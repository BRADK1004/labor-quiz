import streamlit as st
import os, re, json, requests, tempfile
from docx import Document

# ────────────────────────────────
# 환경 변수 / secrets
BING_API_KEY  = st.secrets.get("BING_API_KEY",  os.getenv("BING_API_KEY"))
BING_ENDPOINT = st.secrets.get("BING_ENDPOINT", os.getenv("BING_ENDPOINT",
                    "https://bing-search-labor.cognitiveservices.azure.com"))

# ────────────────────────────────
def bing_search(query: str, top_n: int = 3) -> list[dict]:
    if not BING_API_KEY:
        st.error("BING_API_KEY가 없습니다. .streamlit/secrets.toml 또는 환경변수를 확인하세요.")
        return []

    url = f"{BING_ENDPOINT.rstrip('/')}/bing/v7.0/search"
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    params  = {"q": query, "count": top_n, "textFormat": "Raw"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200:      # 200이 아니면 상세 메시지 출력 후 종료
            st.error(f"Bing API 오류 {resp.status_code}: {resp.text}")
            return []
        data = resp.json().get("webPages", {}).get("value", [])
        return [{"name": d["name"], "url": d["url"], "snippet": d.get("snippet", "")}
                for d in data]
    except (requests.exceptions.ConnectionError,
            requests.exceptions.Timeout) as e:
        st.error(f"네트워크 오류: {e}")
    except Exception as e:
        st.error(f"예기치 못한 오류: {e}")
    return []

# ────────────────────────────────
CHOICE_REGEX = r"([\u2460-\u2464])"     # ①②③④⑤

def load_questions_from_docx(path: str):
    doc   = Document(path)
    text  = " ".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
    idxs  = [(m.start(), m.group()) for m in re.finditer(r"\d+\.\s*", text)]
    idxs.append((len(text), None))

    questions = []
    for i in range(len(idxs) - 1):
        start, _ = idxs[i]
        end,  _  = idxs[i+1]
        segment  = text[start:end].strip()

        parts = re.split(CHOICE_REGEX, segment)
        if len(parts) < 3:          # 보기 부족
            continue
        q_body     = parts[0].split(".", 1)[-1].strip()
        raw_choices = [parts[j] + parts[j+1] for j in range(1, len(parts)-1, 2)]
        if len(raw_choices) < 5:
            continue
        choices = {c[0]: c[1:].strip() for c in raw_choices[:5]}
        questions.append({"question": q_body, "choices": choices})
    return questions

# ────────────────────────────────
def main():
    st.set_page_config(page_title="노무사 기출 (Bing)", page_icon="🧠")
    st.title("🧠 공인노무사 기출문제 퀴즈 (Bing AI 검색)")

    up_file = st.file_uploader("Word (.docx) 기출 파일 업로드", type="docx")
    if up_file is None:
        st.info("먼저 Word 파일을 올려 주세요.")
        return

    # 업로드 파일을 임시 위치에 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(up_file.read())
        temp_path = tmp.name

    try:
        questions = load_questions_from_docx(temp_path)
    finally:
        os.remove(temp_path)        # 파일 정리

    if not questions:
        st.error("문제 파싱 실패: ‘숫자. 문제 ①보기…’ 형식인지 확인하세요.")
        return

    idx = st.number_input("문제 번호", 1, len(questions), 1, key="idx")
    q   = questions[idx-1]

    st.subheader(f"문제 {idx}")
    st.markdown(q["question"])

    sel = st.radio(
        "보기 선택",
        list(q["choices"].keys()),
        format_func=lambda k: f"{k}. {q['choices'][k]}",
        key="sel",
    )

    if st.button("검색 결과 보기"):
        with st.spinner("Bing 검색 중..."):
            results = bing_search(f"{q['question']} 정답 해설")

        if not results:
            st.warning("검색 결과가 없거나 API 문제일 수 있습니다. 로그를 확인하세요.")
        else:
            st.caption("🔎 상위 검색 결과")
            for r in results:
                st.markdown(f"- [{r['name']}]({r['url']})  \n  {r['snippet']}")
            st.info("자세한 해설은 링크를 참고하세요.")

if __name__ == "__main__":
    main()

import streamlit as st
import os
import re
import requests
from docx import Document

# ────────────────────────────────
# Azure Bing Search API 키 및 엔드포인트 (Secrets에 등록)
BING_API_KEY  = os.getenv("BING_API_KEY")
BING_ENDPOINT = os.getenv("BING_ENDPOINT", "https://bing-search-labor.cognitiveservices.azure.com")

# ────────────────────────────────
# Bing 검색 함수 (최대 top_n개 결과 반환)
def bing_search(query: str, top_n: int = 3):
    if not BING_API_KEY:
        return []
    url = f"{BING_ENDPOINT}/v7.0/search"   # ← 여기 경로 수정
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    params  = {"q": query, "count": top_n, "textFormat": "Raw"}
    resp = requests.get(url, headers=headers, params=params, timeout=10)
    if resp.status_code != 200:
        return []
    data = resp.json().get("webPages", {}).get("value", [])
    return [
        {
            "name": item["name"],
            "url": item["url"],
            "snippet": item.get("snippet", "")
        }
        for item in data
    ]

# ────────────────────────────────
# Word(.docx) → 문제·보기 파싱 정규식
CHOICE_REGEX = r"([\u2460-\u2464])"  # ①②③④⑤

def load_questions_from_docx(path: str):
    doc = Document(path)
    text = " ".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
    start_idx = [(m.start(), m.group()) for m in re.finditer(r"(\d+)\. ", text)]
    start_idx.append((len(text), None))

    questions = []
    for i in range(len(start_idx) - 1):
        begin, _ = start_idx[i]
        end, _ = start_idx[i + 1]
        segment = text[begin:end].strip()

        parts = re.split(CHOICE_REGEX, segment)
        if len(parts) < 3:
            continue
        q_body = parts[0].split(". ", 1)[-1].strip()
        raw_choices = [parts[j] + parts[j + 1] for j in range(1, len(parts) - 1, 2)]
        if len(raw_choices) < 5:
            continue
        choices = {c[0]: c[1:].strip() for c in raw_choices[:5]}
        questions.append({"question": q_body, "choices": choices})
    return questions

# ────────────────────────────────
# Streamlit UI

def main():
    st.set_page_config(page_title="노무사 기출 (Bing)", page_icon="🧠")
    st.title("🧠 공인노무사 기출문제 퀴즈 (Bing AI 검색)")

    up_file = st.file_uploader("Word .docx 기출 파일 업로드", type="docx")
    if not up_file:
        st.info("먼저 Word 파일을 올려 주세요")
        return

    with open("temp.docx", "wb") as f:
        f.write(up_file.read())

    questions = load_questions_from_docx("temp.docx")
    if not questions:
        st.error("문제 형식을 파싱하지 못했습니다")
        return

    idx = st.number_input("문제 번호", 1, len(questions), 1)
    q = questions[idx - 1]

    st.subheader(f"문제 {idx}")
    st.write(q["question"])

    sel = st.radio(
        "보기 선택",
        list(q["choices"].keys()),
        format_func=lambda k: f"{k}. {q['choices'][k]}"
    )

    if st.button("검색 결과 보기"):
        with st.spinner("Bing 검색 중..."):
            result_list = bing_search(f"{q['question']} 정답 해설")
        if not result_list:
            st.warning("검색 결과가 없거나 API 키 미설정")
        else:
            st.markdown("---")
            st.caption("🔎 상위 검색 결과")
            for r in result_list:
                st.markdown(f"- [{r['name']}]({r['url']})  \n  {r['snippet']}")
            st.markdown("---")
            st.info("원문 해설은 링크를 참고하여 확인하세요.")

if __name__ == "__main__":
    main()

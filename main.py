import streamlit as st
import os
import re
import requests
from docx import Document

# ─────────────────────────────────────────────
# 🔑 Bing Search API (Azure) 키 및 엔드포인트
#    Streamlit Cloud → Settings → Secrets 등록 필요
# ─────────────────────────────────────────────
BING_API_KEY = os.getenv("BING_API_KEY")
RAW_ENDPOINT = os.getenv("BING_ENDPOINT", "").rstrip("/")
if not RAW_ENDPOINT:
    RAW_ENDPOINT = "https://bing-search-labor.cognitiveservices.azure.com"

SEARCH_URL = f"{RAW_ENDPOINT}/bing/v7.0/search"

# ─────────────────────────────────────────────
# Bing 검색 함수
# ─────────────────────────────────────────────
def bing_search(query: str, top_n: int = 3):
    if not BING_API_KEY:
        st.warning("❗️BING_API_KEY가 설정되어 있지 않습니다.")
        return []
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    params = {"q": query, "count": top_n, "textFormat": "Raw"}

    try:
        resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        st.error(f"🔑 Bing 호출 오류: {e}")
        return []

    items = resp.json().get("webPages", {}).get("value", [])
    return [
        {"name": it["name"], "url": it["url"], "snippet": it.get("snippet", "")}
        for it in items
    ]

# ─────────────────────────────────────────────
# Word(.docx) → 문제·보기 파싱
# ─────────────────────────────────────────────
CHOICE_REGEX = r"([\u2460-\u2464])"  # ①②③④⑤

def load_questions_from_docx(path: str):
    doc = Document(path)
    text = " ".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
    idx = [(m.start(), m.group()) for m in re.finditer(r"(\d+)\. ", text)]
    idx.append((len(text), None))

    questions = []
    for i in range(len(idx) - 1):
        begin, _ = idx[i]
        end, _ = idx[i + 1]
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

# ─────────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────────
def main():
    st.set_page_config(page_title="노무사 기출 (Bing)", page_icon="🧠")
    st.title("🧠 공인노무사 기출문제 퀴즈 (Bing AI 검색)")

    up_file = st.file_uploader("📄 Word .docx 기출 파일 업로드", type="docx")
    if not up_file:
        st.info("먼저 Word 파일을 올려 주세요.")
        return

    with open("temp.docx", "wb") as f:
        f.write(up_file.read())
    questions = load_questions_from_docx("temp.docx")

    if not questions:
        st.error("❌ 문제 형식을 파싱하지 못했습니다.")
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

    if st.button("🔍 검색 결과 보기"):
        with st.spinner("Bing 검색 중..."):
            result_list = bing_search(f"{q['question']} 정답 해설")
        if not result_list:
            st.warning("검색 결과가 없거나 키 설정이 누락되었습니다.")
        else:
            st.markdown("---")
            st.caption("🔎 상위 검색 결과")
            for r in result_list:
                st.markdown(f"- [{r['name']}]({r['url']})  \n  {r['snippet']}")
            st.markdown("---")
            st.info("📘 더 자세한 해설은 링크를 참고하세요.")

if __name__ == "__main__":
    main()

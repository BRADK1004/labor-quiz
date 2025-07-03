import streamlit as st
import os
import re
from docx import Document
from openai import OpenAI
from dotenv import load_dotenv

# -----------------------------------
# 환경 설정 및 OpenAI 클라이언트
# -----------------------------------
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------------
# 문제 파싱 로직 (줄바꿈 없어도 동작)
# -----------------------------------

def load_questions_from_docx(path: str):
    """Word(.docx) 파일 안의 텍스트에서 문제‑보기 세트를 파싱한다.
    ‑ 줄바꿈이 없더라도 문제 번호(1. 2. …)와 보기 번호(①~⑤) 패턴으로 분리
    ‑ 반환값: [{"question": str, "choices": {"①": txt, …}}]
    """
    doc = Document(path)
    text = " ".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])  # 줄바꿈 무시, 공백 하나로 연결

    # 문제 번호 위치 모두 찾기
    idx = [(m.start(), m.group()) for m in re.finditer(r"(\d+)\. ", text)]
    idx.append((len(text), None))  # 끝 표시

    questions = []
    for i in range(len(idx) - 1):
        start, label = idx[i]
        end, _ = idx[i + 1]
        segment = text[start:end].strip()

        # 문제 본문과 보기 분리
        split_choice = re.split(r"([①②③④⑤])", segment)
        if len(split_choice) < 3:
            continue  # 보기 5개 없으면 스킵
        question_part = split_choice[0].split(". ", 1)[-1].strip()  # 번호 제거

        # choices dict
        choices_raw = [split_choice[j] + split_choice[j + 1] for j in range(1, len(split_choice) - 1, 2)]
        if len(choices_raw) < 5:
            continue
        choices = {c[0]: c[1:].strip() for c in choices_raw[:5]}  # ①~⑤

        questions.append({"question": question_part, "choices": choices})
    return questions

# -----------------------------------
# GPT 호출 함수
# -----------------------------------

def ask_gpt(question: str, choice_key: str, choice_text: str):
    prompt = (
        "다음은 공인노무사 기출 객관식 문제이다.\n"
        f"문제: {question}\n"
        f"선택한 보기: {choice_key}. {choice_text}\n\n"
        "선택이 맞으면 \"당신의 답: O\" 형태로, 틀리면 \"당신의 답: X\" 형태로 시작하고, 이어서 정답(숫자형 예: ③)과 간단한 해설을 제시하라." )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "당신은 대한민국 노동법 전문가입니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()

# -----------------------------------
# Streamlit UI
# -----------------------------------

def main():
    st.set_page_config(page_title="노무사 기출 퀴즈", page_icon="📚", layout="wide")
    st.title("📚 공인노무사 기출문제 퀴즈 with GPT")

    base = os.path.join(os.path.expanduser("~"), "Desktop", "노무사 학습", "노무사 기출문제")
    files = [f for f in os.listdir(base) if f.endswith(".docx")]
    if not files:
        st.error("워드(.docx) 파일이 없습니다. 폴더를 확인하세요.")
        return

    file_sel = st.selectbox("문제 파일 선택", files)

    qs = load_questions_from_docx(os.path.join(base, file_sel))
    if not qs:
        st.error("문제/보기 형식을 인식할 수 없습니다. 워드 파일을 확인하세요.")
        return

    # 문제 번호 입력 (1~N)
    q_num = st.number_input("문제 번호", min_value=1, max_value=len(qs), step=1)
    prob = qs[q_num - 1]

    st.markdown(f"#### 문제 {q_num}")
    st.write(prob["question"])

    # 라디오 버튼으로 보기 선택
    choice_key = st.radio("선택지", list(prob["choices"].keys()), format_func=lambda k: f"{k}. {prob['choices'][k]}")

    if st.button("정답 확인 및 해설"):
        with st.spinner("GPT가 답변 중..."):
            explanation = ask_gpt(prob['question'], choice_key, prob['choices'][choice_key])
        st.success(explanation)

if __name__ == "__main__":
    main()
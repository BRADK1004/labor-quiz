import streamlit as st
import os
import re
import requests
from docx import Document

# ────────────────────────────────
# Azure Bing Search API 키 및 엔드포인트 (Secrets에 등록)
# Streamlit Secrets에서 API 키를 가져옵니다.
# 로컬 개발 시 .streamlit/secrets.toml 파일에 BING_API_KEY = "YOUR_API_KEY" 형식으로 저장해야 합니다.
BING_API_KEY = os.getenv("BING_API_KEY")

# Bing Search API 엔드포인트를 설정합니다.
# 이 값은 Azure Portal의 Bing Search 리소스 '키 및 엔드포인트' 섹션에서 확인한
# 정확한 기본 엔드포인트 URL이어야 합니다.
# 예: "https://YOUR_RESOURCE_NAME.cognitiveservices.azure.com"
BING_ENDPOINT = os.getenv("BING_ENDPOINT", "https://bing-search-labor.cognitiveservices.azure.com")

# ────────────────────────────────
# Bing 검색 함수 (최대 top_n개 결과 반환)
def bing_search(query: str, top_n: int = 3):
    if not BING_API_KEY:
        st.error("오류: BING_API_KEY가 설정되지 않았습니다. Streamlit Secrets 또는 환경 변수를 확인해주세요.")
        return []

    # HTTP 404 오류는 요청 URL 경로가 잘못되었을 때 발생합니다.
    # BING_ENDPOINT의 마지막 슬래시를 제거하여 중복 슬래시를 방지하고,
    # 가장 일반적인 Bing Web Search API v7 경로인 '/v7.0/search'를 붙여 시도합니다.
    # 만약 Azure Portal의 엔드포인트가 이미 '/v7.0/search'를 포함한다면,
    # url = BING_ENDPOINT.rstrip('/') 또는 url = BING_ENDPOINT 로 설정해야 할 수도 있습니다.
    # 사용하시는 리소스가 Bing Custom Search API라면 엔드포인트 구조가 다를 수 있습니다.
    url = f"{BING_ENDPOINT.rstrip('/')}/v7.0/search" # <-- 이 부분을 다시 수정했습니다.
    
    # 디버깅을 위해 생성된 URL을 콘솔에 출력합니다.
    # Streamlit 앱이 배포된 환경에서는 로그를 통해 확인 가능합니다.
    print(f"Bing Search API 요청 URL: {url}")
    
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    params  = {"q": query, "count": top_n, "textFormat": "Raw"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status() # HTTP 에러 발생 시 예외를 발생시킵니다.

        data = resp.json().get("webPages", {}).get("value", [])
        return [
            {
                "name": item["name"],
                "url": item["url"],
                "snippet": item.get("snippet", "")
            }
            for item in data
        ]
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP 오류 발생: {e.response.status_code} - {e.response.text}")
        # 중요: 응답 본문을 출력하여 서버가 제공하는 자세한 오류 내용을 확인합니다.
        # 이 정보가 404 오류의 정확한 원인을 파악하는 데 도움이 될 수 있습니다.
        print(f"HTTP Error Response Body: {e.response.text}")
        return []
    except requests.exceptions.ConnectionError as e:
        st.error(f"네트워크 연결 오류: Bing API 서버에 연결할 수 없습니다. 엔드포인트나 인터넷 연결을 확인해주세요. ({e})")
        return []
    except requests.exceptions.Timeout:
        st.error("요청 시간 초과: Bing API 응답이 너무 오래 걸립니다. 다시 시도해주세요.")
        return []
    except requests.exceptions.RequestException as e:
        st.error(f"요청 중 알 수 없는 오류 발생: {e}")
        return []
    except Exception as e:
        st.error(f"Bing 검색 중 예기치 않은 오류 발생: {e}")
        return []

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
    st.title("  공인노무사 기출문제 퀴즈 (Bing AI 검색)")

    up_file = st.file_uploader("Word .docx 기출 파일 업로드", type="docx")
    if not up_file:
        st.info("먼저 Word 파일을 올려 주세요")
        return

    # 업로드된 파일을 임시 파일로 저장
    temp_file_path = "temp.docx"
    with open(temp_file_path, "wb") as f:
        f.write(up_file.read())

    questions = load_questions_from_docx(temp_file_path)
    if not questions:
        st.error("문제 형식을 파싱하지 못했습니다. 문제 형식이 '숫자. 문제 내용 ① 보기 내용 ② 보기 내용...'과 같은지 확인해주세요.")
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
            # 검색 쿼리에 문제 내용과 '정답 해설'을 포함하여 검색합니다.
            result_list = bing_search(f"{q['question']} 정답 해설")
        
        if not result_list:
            st.warning("검색 결과가 없거나 API 키/엔드포인트 설정 문제일 수 있습니다. 위에 표시된 오류 메시지를 확인해주세요.")
        else:
            st.markdown("---")
            st.caption("🔎 상위 검색 결과")
            for r in result_list:
                st.markdown(f"- [{r['name']}]({r['url']})  \n  {r['snippet']}")
            st.markdown("---")
            st.info("원문 해설은 링크를 참고하여 확인하세요.")

if __name__ == "__main__":
    main()
 
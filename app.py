import streamlit as st
import requests

st.set_page_config(page_title="API 테스트", page_icon="🔧", layout="centered")

st.title("🔧 안전Dream API 연동 테스트")

ESNTL_ID = "10001061"
AUTH_KEY = "bc9ff0e7eedc4228"
FIND_CHILD_URL = "https://www.safe182.go.kr/api/lcm/findChildList.do"

payload = {
    "esntlId": ESNTL_ID,
    "authKey": AUTH_KEY,
    "rowSize": "10",
    "page": "1",
}

st.write("보내는 요청 정보:")
st.json(payload)

try:
    resp = requests.post(FIND_CHILD_URL, data=payload, timeout=10)
    st.write("HTTP 상태 코드:", resp.status_code)
    st.write("응답 원문(text):")
    st.code(resp.text[:3000])

    try:
        data = resp.json()
        st.write("파싱된 JSON:")
        st.json(data)
    except Exception as e:
        st.error("JSON 파싱 실패: " + str(e))

except Exception as e:
    st.error("요청 자체 실패: " + str(e))

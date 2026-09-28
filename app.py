import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="실종아동·취약계층 실종정보 알리미",
    page_icon="🔍",
    layout="centered"
)

css_style = """
<style>
body, .stApp { background-color: #F3F5F8; }

.block-container {
    padding-top: 3rem;
    max-width: 560px;
    margin: 0 auto;
}

.hero-box {
    background: linear-gradient(135deg, #0B2545, #1B3B6F);
    border-radius: 20px;
    padding: 40px 28px;
    text-align: center;
    box-shadow: 0 8px 24px rgba(11,37,69,0.25);
    margin-bottom: 24px;
}
.hero-icon {
    font-size: 52px;
    margin-bottom: 14px;
}
.hero-title {
    color: white !important;
    font-size: 26px;
    font-weight: 900;
    margin-bottom: 8px;
    letter-spacing: -0.3px;
}
.hero-sub {
    color: #BFD0EA !important;
    font-size: 15px;
    font-weight: 500;
    line-height: 1.6;
}

.status-box {
    background: white;
    border: 1px solid #E7EAEE;
    border-left: 6px solid #C62828;
    border-radius: 14px;
    padding: 20px 22px;
    margin-bottom: 20px;
    box-shadow: 0 2px 10px rgba(15,30,60,0.06);
}
.status-badge {
    display: inline-block;
    background: #FFF3E0;
    color: #E65100 !important;
    font-size: 12px;
    font-weight: 800;
    padding: 5px 12px;
    border-radius: 999px;
    margin-bottom: 10px;
}
.status-text {
    font-size: 15px;
    font-weight: 700;
    color: #222 !important;
    line-height: 1.7;
}

.info-grid {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
}
.info-card {
    flex: 1;
    background: white;
    border-radius: 14px;
    padding: 16px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(15,30,60,0.06);
}
.info-card-icon { font-size: 24px; margin-bottom: 6px; }
.info-card-label { font-size: 12.5px; font-weight: 700; color: #5A6B85 !important; }

.footer-note {
    text-align: center;
    font-size: 12px;
    color: #8894A6 !important;
    margin-top: 30px;
}
</style>
"""
st.markdown(css_style, unsafe_allow_html=True)

st.markdown(
    '<div class="hero-box">'
    '<div class="hero-icon">🔍</div>'
    '<div class="hero-title">실종아동·취약계층 실종정보 알리미</div>'
    '<div class="hero-sub">아동, 지적·자폐성·정신장애인, 치매질환자 등<br>실종정보를 실시간으로 안내하는 서비스입니다.</div>'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="status-box">'
    '<div class="status-badge">🚧 준비 중</div>'
    '<div class="status-text">현재 경찰청 안전Dream(safe182) OPEN API 연동을 준비하고 있습니다.<br>'
    '서비스 오픈 시 실종 발생 현황을 실시간으로 확인하실 수 있습니다.</div>'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="info-grid">'
    '<div class="info-card"><div class="info-card-icon">👶</div><div class="info-card-label">정상아동<br>(18세 미만)</div></div>'
    '<div class="info-card"><div class="info-card-icon">🧩</div><div class="info-card-label">지적·자폐성<br>장애인</div></div>'
    '<div class="info-card"><div class="info-card-icon">🧓</div><div class="info-card-label">치매<br>질환자</div></div>'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="footer-note">자료 출처: 경찰청 · 안전Dream(safe182.go.kr)<br>'
    + datetime.now().strftime("%Y.%m.%d %H:%M") + ' 기준</div>',
    unsafe_allow_html=True
)

import streamlit as st
import requests
import pandas as pd
import base64
from datetime import datetime
import plotly.graph_objects as go

# ────────────────────────────────
# 기본 설정
# ────────────────────────────────
st.set_page_config(
    page_title="실종아동·취약계층 실종정보 알리미",
    page_icon="🔍",
    layout="wide"
)

ESNTL_ID = "10001061"
AUTH_KEY = "bc9ff0e7eedc4228"
FIND_CHILD_URL = "https://www.safe182.go.kr/api/lcm/findChildList.do"

TARGET_LABELS = {
    "010": "정상아동(18세미만)",
    "020": "가출인",
    "040": "시설보호무연고자",
    "060": "지적장애인",
    "061": "지적장애인(18세미만)",
    "062": "지적장애인(18세이상)",
    "070": "치매질환자",
    "080": "기타"
}

TARGET_COLOR = {
    "010": "#1565C0",
    "020": "#6D4C41",
    "040": "#546E7A",
    "060": "#7B1FA2",
    "061": "#7B1FA2",
    "062": "#7B1FA2",
    "070": "#2E7D32",
    "080": "#455A64"
}

session = requests.Session()

# ────────────────────────────────
# 데이터 불러오기 (5분 캐시)
# ────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def fetch_all_missing(max_rows=500):
    all_list = []
    page = 1
    row_size = 100
    total_count = 0
    while True:
        payload = {
            "esntlId": ESNTL_ID,
            "authKey": AUTH_KEY,
            "rowSize": str(row_size),
            "page": str(page),
        }
        try:
            resp = session.post(FIND_CHILD_URL, data=payload, timeout=10)
            data = resp.json()
        except Exception:
            break

        if data.get("result") != "00":
            break

        total_count = data.get("totalCount", 0)
        rows = data.get("list", [])
        all_list.extend(rows)

        if len(rows) < row_size or len(all_list) >= max_rows or len(all_list) >= total_count:
            break
        page += 1

    df = pd.DataFrame(all_list)
    return df, total_count

def parse_date(v):
    try:
        return datetime.strptime(str(v), "%Y%m%d").strftime("%Y.%m.%d")
    except Exception:
        return "-"

# ────────────────────────────────
# CSS (헤더 + 실시간 스크롤 배너 + 카드)
# ────────────────────────────────
st.markdown("""
<style>
.stApp { background-color: #F3F5F8; }
.block-container { padding-top: 1.2rem; max-width: 1100px; margin: 0 auto; }

.hero-box {
    background: linear-gradient(135deg, #0B2545, #1B3B6F);
    border-radius: 20px;
    padding: 30px 28px;
    text-align: center;
    margin-bottom: 14px;
}
.hero-title { color: white !important; font-size: 26px; font-weight: 900; }
.hero-sub { color: #BFD0EA !important; font-size: 14px; margin-top: 6px; }

/* 실시간 스크롤 배너 */
.ticker-wrap {
    background: #C62828;
    border-radius: 12px;
    overflow: hidden;
    white-space: nowrap;
    padding: 10px 0;
    margin-bottom: 20px;
    box-shadow: 0 2px 10px rgba(198,40,40,0.35);
}
.ticker-move {
    display: inline-block;
    padding-left: 100%;
    animation: ticker-scroll 22s linear infinite;
    color: white;
    font-size: 14.5px;
    font-weight: 700;
}
.ticker-move span { margin-right: 48px; }
@keyframes ticker-scroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-100%); }
}

.stat-row { display: flex; gap: 10px; margin-bottom: 18px; flex-wrap: wrap; }
.stat-card { flex: 1; min-width: 120px; background: white; border-radius: 14px; padding: 14px; text-align: center; box-shadow: 0 2px 8px rgba(15,30,60,0.06); }
.stat-num { font-size: 22px; font-weight: 900; color: #0B2545; }
.stat-label { font-size: 12px; color: #5A6B85; font-weight: 700; margin-top: 2px; }

.person-card { background: white; border-radius: 14px; padding: 14px; box-shadow: 0 2px 8px rgba(15,30,60,0.06); margin-bottom: 14px; }
.person-badge { display:inline-block; font-size:11px; font-weight:800; color:white; padding:3px 9px; border-radius:999px; margin-bottom:6px; }
.person-name { font-size:16px; font-weight:900; color:#111; }
.person-info { font-size:13px; color:#444; margin-top:4px; line-height:1.5; }

.footer-note { text-align:center; font-size:12px; color:#8894A6; margin-top:26px; }

/* 하단 3개년 통계 섹션 */
.summary-title { font-size:20px; font-weight:900; color:#0B2545; margin: 30px 0 14px 0; }
.summary-card { background:white; border-radius:16px; padding:20px; box-shadow:0 2px 10px rgba(15,30,60,0.07); margin-bottom:16px; }
.summary-card-title { font-size:14px; font-weight:800; color:#5A6B85; margin-bottom:8px; }
.summary-big { font-size:26px; font-weight:900; color:#0B2545; }
.summary-sub { font-size:12.5px; color:#8894A6; margin-top:4px; }
.badge-found { background:#E8F5E9; color:#2E7D32 !important; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:800; }
.badge-missing { background:#FFEBEE; color:#C62828 !important; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:800; }
.source-note { font-size:11px; color:#B0B8C4; margin-top:10px; }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────
# 헤더
# ────────────────────────────────
st.markdown(
    '<div class="hero-box">'
    '<div class="hero-title">🔍 실종아동·취약계층 실종정보 알리미</div>'
    '<div class="hero-sub">아동, 지적·자폐성 장애인, 치매질환자 등 실종정보를 실시간으로 안내합니다</div>'
    '</div>', unsafe_allow_html=True
)

df, total_count = fetch_all_missing()

if df.empty:
    st.error("데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")
    st.stop()

df["target_label"] = df["writngTrgetDscd"].map(TARGET_LABELS).fillna("기타")
df["date_fmt"] = df["occrde"].apply(parse_date)

# ────────────────────────────────
# 실시간 스크롤 배너 (최근 등록 20건)
# ────────────────────────────────
recent_df = df.sort_values("occrde", ascending=False).head(20)
ticker_items = ""
for _, row in recent_df.iterrows():
    ticker_items += (
        f"<span>🚨 [{row['target_label']}] {row.get('nm','정보없음')} · "
        f"{row.get('sexdstnDscd','-')} · {row.get('age','-')}세 · "
        f"{row['date_fmt']} 발생 · {row.get('occrAdres','-')}</span>"
    )

st.markdown(
    f'<div class="ticker-wrap"><div class="ticker-move">{ticker_items}</div></div>',
    unsafe_allow_html=True
)

# ────────────────────────────────
# 상단 통계 배지
# ────────────────────────────────
cat_counts = df["target_label"].value_counts()
stat_html = f'<div class="stat-row"><div class="stat-card"><div class="stat-num">{total_count:,}</div><div class="stat-label">전체 등록</div></div>'
for label, cnt in cat_counts.items():
    stat_html += f'<div class="stat-card"><div class="stat-num">{cnt}</div><div class="stat-label">{label}</div></div>'
stat_html += "</div>"
st.markdown(stat_html, unsafe_allow_html=True)

tab_list, tab_stat = st.tabs(["📋 실시간 목록", "📊 통계"])

# ────────────────────────────────
# 탭 1: 목록
# ────────────────────────────────
with tab_list:
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        sel_target = st.multiselect("대상구분", options=sorted(df["target_label"].unique()), default=[])
    with col2:
        sel_gender = st.multiselect("성별", options=sorted(df["sexdstnDscd"].dropna().unique()), default=[])
    with col3:
        keyword = st.text_input("이름/지역 검색", "")

    filtered = df.copy()
    if sel_target:
        filtered = filtered[filtered["target_label"].isin(sel_target)]
    if sel_gender:
        filtered = filtered[filtered["sexdstnDscd"].isin(sel_gender)]
    if keyword:
        filtered = filtered[
            filtered["nm"].astype(str).str.contains(keyword, na=False) |
            filtered["occrAdres"].astype(str).str.contains(keyword, na=False)
        ]

    st.write(f"검색 결과: **{len(filtered)}건**")

    PAGE_SIZE = 12
    if "page_no" not in st.session_state:
        st.session_state.page_no = 1

    total_pages = max(1, (len(filtered) - 1) // PAGE_SIZE + 1)
    st.session_state.page_no = min(st.session_state.page_no, total_pages)

    start = (st.session_state.page_no - 1) * PAGE_SIZE
    page_df = filtered.iloc[start:start + PAGE_SIZE]

    cols = st.columns(3)
    for i, (_, row) in enumerate(page_df.iterrows()):
        with cols[i % 3]:
            badge_color = TARGET_COLOR.get(row["writngTrgetDscd"], "#455A64")
            st.markdown(
                f'<div class="person-card">'
                f'<span class="person-badge" style="background:{badge_color}">{row["target_label"]}</span>'
                f'<div class="person-name">{row.get("nm", "정보없음")}</div>'
                f'<div class="person-info">'
                f'{row.get("sexdstnDscd","-")} · 당시 {row.get("age","-")}세 (현재 {row.get("ageNow","-")}세)<br>'
                f'발생일: {row["date_fmt"]}<br>'
                f'발생장소: {row.get("occrAdres","-")}<br>'
                f'특징: {row.get("etcSpfeatr") or "정보없음"}'
                f'</div></div>',
                unsafe_allow_html=True
            )
            photo_b64 = row.get("tknphotoFile")
            if isinstance(photo_b64, str) and len(photo_b64) > 100:
                try:
                    img_bytes = base64.b64decode(photo_b64)
                    st.image(img_bytes, width=150)
                except Exception:
                    st.write("📷 사진 로드 실패")

    nav1, nav2, nav3 = st.columns([1, 2, 1])
    with nav1:
        if st.button("◀ 이전", disabled=st.session_state.page_no <= 1):
            st.session_state.page_no -= 1
            st.rerun()
    with nav2:
        st.markdown(f"<div style='text-align:center'>{st.session_state.page_no} / {total_pages} 페이지</div>", unsafe_allow_html=True)
    with nav3:
        if st.button("다음 ▶", disabled=st.session_state.page_no >= total_pages):
            st.session_state.page_no += 1
            st.rerun()

# ────────────────────────────────
# 탭 2: 통계 (API 실시간 데이터)
# ────────────────────────────────
with tab_stat:
    bar_fig = go.Figure(go.Bar(
        x=cat_counts.index.tolist(),
        y=cat_counts.values.tolist(),
        marker_color="#1B3B6F",
        text=cat_counts.values.tolist(),
        textposition="outside"
    ))
    bar_fig.update_layout(title="대상구분별 등록 건수 (실시간)", height=350, margin=dict(t=50, b=30))
    st.plotly_chart(bar_fig, use_container_width=True, config={"staticPlot": True, "displayModeBar": False})

    gender_counts = df["sexdstnDscd"].value_counts()
    pie_fig = go.Figure(go.Pie(
        labels=gender_counts.index.tolist(),
        values=gender_counts.values.tolist(),
        marker=dict(colors=["#1565C0", "#C62828"])
    ))
    pie_fig.update_layout(title="성별 비율 (실시간)", height=350, margin=dict(t=50, b=30))
    st.plotly_chart(pie_fig, use_container_width=True, config={"staticPlot": True, "displayModeBar": False})

# ────────────────────────────────
# 최근 3년 실종 통계 종합 (경찰청·e-나라지표 공식 통계)
# ────────────────────────────────
st.markdown('<div class="summary-title">📈 최근 3년(2023~2025) 실종 통계 종합</div>', unsafe_allow_html=True)

years = ["2023", "2024", "2025"]
child_elderly_reports = [48745, 49624, 54569]   # 실종아동등(아동+장애인+치매환자) 신고접수
adult_reports = [74847, 71854, None]            # 성인(가출인) 신고접수 - 2025년 확정치 미공개

trend_fig = go.Figure()
trend_fig.add_trace(go.Bar(
    x=years, y=child_elderly_reports, name="실종아동등(아동·장애인·치매환자)",
    marker_color="#1565C0", text=child_elderly_reports, textposition="outside"
))
trend_fig.add_trace(go.Bar(
    x=years, y=adult_reports, name="성인 실종신고(가출인)",
    marker_color="#EF6C00", text=[f"{v:,}" if v else "집계중" for v in adult_reports], textposition="outside"
))
trend_fig.update_layout(
    barmode="group", height=360, margin=dict(t=30, b=30),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
)
st.plotly_chart(trend_fig, use_container_width=True, config={"staticPlot": True, "displayModeBar": False})

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        '<div class="summary-card">'
        '<div class="summary-card-title">2024년 실종아동등 발견 현황</div>'
        '<div class="summary-big">48,751건 <span class="badge-found">발견</span></div>'
        '<div class="summary-sub">전체 접수 49,624건 중 발견율 99.75%</div>'
        '</div>', unsafe_allow_html=True
    )
with c2:
    st.markdown(
        '<div class="summary-card">'
        '<div class="summary-card-title">2024년 영구(장기) 미발견</div>'
        '<div class="summary-big">121건 <span class="badge-missing">미발견</span></div>'
        '<div class="summary-sub">아동 64명 · 장애인 41명 · 치매환자 16명 (미발견율 0.25%)</div>'
        '</div>', unsafe_allow_html=True
    )
with c3:
    st.markdown(
        '<div class="summary-card">'
        '<div class="summary-card-title">실종 재신고(오신고 유사) 현황</div>'
        '<div class="summary-big">약 15만건</div>'
        '<div class="summary-sub">최근 5년간 해제 후 재신고, 이 중 약 30%가 성인 사례</div>'
        '</div>', unsafe_allow_html=True
    )

st.markdown(
    '<div class="source-note">※ 위 3개년 통계는 경찰청 실종아동등 프로파일링 시스템 및 e-나라지표(index.go.kr) 공식 발표 자료를 기준으로 작성되었습니다. '
    '2025년 성인(가출인) 신고 확정치는 아직 공식 발표되지 않아 "집계중"으로 표시되며, "오신고" 단독 통계는 공개되지 않아 가장 근접한 "재신고" 통계로 대체 표기했습니다.</div>',
    unsafe_allow_html=True
)

# ────────────────────────────────
# 푸터
# ────────────────────────────────
st.markdown(
    f'<div class="footer-note">자료 출처: 경찰청 · 안전Dream(safe182.go.kr) · e-나라지표<br>'
    f'{datetime.now().strftime("%Y.%m.%d %H:%M")} 기준 · 5분마다 자동 갱신</div>',
    unsafe_allow_html=True
)

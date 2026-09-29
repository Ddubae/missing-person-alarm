import re
import datetime as dt
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import streamlit as st

st.set_page_config(page_title="대한민국 지진 현황 알리미", layout="wide", page_icon="🌍")

# ────────────────────────────────────────────────────────────
# 1. 설정값 (API 키는 본인 발급 키로 교체)
# ────────────────────────────────────────────────────────────
KMA_KEY = "여기에_기상청_API_키_입력"
SAFEMAP_KEY = "여기에_생활안전지도_API_키_입력"
KMA_URL = "https://apis.data.go.kr/1360000/EqkInfoService/getEqkMsg"
SAFEMAP_URL = "https://www.safemap.go.kr/openapi2/IF_0030"

# 남한만 보이도록 좌표 범위 축소
KOREA_BOUNDS = [[33.0, 125.2], [38.65, 129.6]]

PROVINCE_CENTER = {
    "서울": [37.5665, 126.9780], "부산": [35.1796, 129.0756], "대구": [35.8714, 128.6014],
    "인천": [37.4563, 126.7052], "광주": [35.1595, 126.8526], "대전": [36.3504, 127.3845],
    "울산": [35.5384, 129.3114], "경기": [37.4138, 127.5183], "강원": [37.8228, 128.1555],
    "충북": [36.8000, 127.7000], "충남": [36.5184, 126.8000], "전북": [35.7175, 127.1530],
    "전남": [34.8679, 126.9910], "경북": [36.4919, 128.8889], "경남": [35.4606, 128.2132],
    "제주": [33.4996, 126.5312],
}

# 발생빈도 색상 (연한 핑크 → 진한 자주)
BIN_COLORS = {
    "0~10건": "#F5B7C4",
    "11~50건": "#E85D8A",
    "51~100건": "#B3123B",
    "100건 초과": "#5C0A22",
}

# 진도(강도) 색상 - 기상청 표준 진도 색상표 기반
INTENSITY_COLORS = {
    1: "#E8F5E9", 2: "#C6E6BD", 3: "#98D583", 4: "#FCE38A",
    5: "#FDBB5E", 6: "#F6842C", 7: "#E4402A", 8: "#B71C1C",
    9: "#7A0C1E", 10: "#4A0512", 11: "#2E0209", 12: "#000000",
}

# 진도 1~4단계 설명 + 참고영상 (수동 텍스트 라벨용)
INTENSITY_LEVELS = {
    1: {"label": "진도 Ⅰ", "desc": "대부분 느끼지 못하나 정밀 기기에는 감지됨.",
        "video": "https://www.youtube.com/watch?v=zO2H4dzGsho"},
    2: {"label": "진도 Ⅱ", "desc": "조용한 상태에서 소수의 사람만 느낄 수 있음.",
        "video": "https://www.youtube.com/watch?v=zO2H4dzGsho"},
    3: {"label": "진도 Ⅲ", "desc": "실내에서 다수가 느끼며 정지한 차량이 약하게 흔들림.",
        "video": "https://www.youtube.com/watch?v=gEf45HNBiK4"},
    4: {"label": "진도 Ⅳ", "desc": "실내 다수, 실외 소수가 느끼며 그릇·창문이 흔들림.",
        "video": "https://www.youtube.com/watch?v=gEf45HNBiK4"},
}

# 행동요령 4단계
SAFETY_STEPS = [
    {"step": "1단계. 평소 대비",
     "desc": "가구·가전제품이 넘어지지 않도록 벽에 단단히 고정하고, 유리창에는 안전필름을 붙여둡니다. "
             "손전등, 응급약품, 생수 등 비상용품을 미리 준비합니다.",
     "video": "https://www.youtube.com/watch?v=zO2H4dzGsho"},
    {"step": "2단계. 흔들리는 동안",
     "desc": "탁자 밑처럼 몸을 보호할 수 있는 튼튼한 곳으로 들어가 몸을 웅크리고, 흔들림이 멈출 때까지 "
             "그 자리에서 기다립니다. 창가나 문틀에는 가까이 가지 않습니다.",
     "video": "https://www.youtube.com/watch?v=gEf45HNBiK4"},
    {"step": "3단계. 흔들림이 멈춘 후",
     "desc": "가스 밸브를 잠그고 전기 차단기를 내려 화재 위험을 없앤 뒤, 신발을 신고 계단을 이용해 "
             "건물 밖으로 신속히 이동합니다. 엘리베이터는 절대 사용하지 않습니다.",
     "video": "https://www.youtube.com/watch?v=BF6LZfE7v8o"},
    {"step": "4단계. 대피 및 대응",
     "desc": "건물 밖으로 나온 뒤에는 담장, 유리창, 간판이 떨어질 수 있는 건물 주변을 피해 운동장이나 "
             "공원 같은 넓은 공터로 이동합니다. 재난문자·라디오로 안전 정보를 계속 확인합니다.",
     "video": "https://www.youtube.com/watch?v=stOUne88yR0"},
]

# ────────────────────────────────────────────────────────────
# 2. 데이터 수집 함수
# ────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_recent_eq(days=3):
    """최근 N일 이내 지진 발생 정보 (safemap API 활용, 페이지 순회)"""
    today = dt.date.today()
    start = today - dt.timedelta(days=days)
    rows, page = [], 1
    while True:
        params = {"serviceKey": SAFEMAP_KEY, "pageNo": page, "numOfRows": 100, "returnType": "JSON"}
        try:
            res = requests.get(SAFEMAP_URL, params=params, timeout=10).json()
        except Exception:
            break
        items = res.get("body", {}).get("items", {}).get("item", [])
        if not items:
            break
        for it in items:
            try:
                d = dt.datetime.strptime(str(it.get("dt", "")), "%Y%m%d").date()
            except Exception:
                continue
            if d < start:
                page = 999999  # 더 이상 과거로 갈 필요 없음 → 루프 종료 유도
                break
            rows.append(it)
        if page >= 999999 or len(items) < 100:
            break
        page += 1
        if page > 10:
            break
    df = pd.DataFrame(rows)
    return _clean_df(df)


@st.cache_data(ttl=3600)
def fetch_history_eq(max_pages=20):
    """전체 이력 데이터 (safemap API, 페이지당 700건씩 순회)"""
    rows, page = [], 1
    total = None
    while True:
        params = {"serviceKey": SAFEMAP_KEY, "pageNo": page, "numOfRows": 700, "returnType": "JSON"}
        try:
            res = requests.get(SAFEMAP_URL, params=params, timeout=15).json()
        except Exception:
            break
        body = res.get("body", {})
        items = body.get("items", {}).get("item", [])
        total = body.get("totalCount", total)
        if not items:
            break
        rows.extend(items)
        if len(rows) >= (total or 0) or page >= max_pages:
            break
        page += 1
    df = pd.DataFrame(rows)
    return _clean_df(df)


def extract_province(loc: str) -> str:
    if not isinstance(loc, str):
        return "기타"
    m = re.match(r"([가-힣]{2,3})\s", loc)
    return m.group(1) if m else loc[:2]


def extract_city(loc: str) -> str:
    """시·군·구까지 포함한 지역명 추출 (예: 경북 경주시)"""
    if not isinstance(loc, str):
        return "기타"
    m = re.match(r"([가-힣]{2,3})\s+([가-힣]+[시군구])", loc)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    m2 = re.match(r"([가-힣]{2,3})", loc)
    return m2.group(1) if m2 else loc


def bin_label(count: int) -> str:
    if count <= 10:
        return "0~10건"
    elif count <= 50:
        return "11~50건"
    elif count <= 100:
        return "51~100건"
    return "100건 초과"


def intensity_color(grade) -> str:
    try:
        g = int(float(grade))
    except (TypeError, ValueError):
        g = 1
    return INTENSITY_COLORS.get(min(max(g, 1), 12), "#999999")


def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.rename(columns={
        "dt": "date_raw", "tm": "time_raw", "mt": "mag", "lc": "location",
        "lat": "lat", "lon": "lon", "inten": "intensity",
    })
    for col in ["mag", "lat", "lon"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "date_raw" in df.columns:
        df["date"] = pd.to_datetime(df["date_raw"], format="%Y%m%d", errors="coerce")
        df["year"] = df["date"].dt.year
    if "location" in df.columns:
        df["province"] = df["location"].apply(extract_province)
        df["city"] = df["location"].apply(extract_city)
    # 동일 시각·위치 중복 제거
    dedup_cols = [c for c in ["date", "lat", "lon", "mag"] if c in df.columns]
    if dedup_cols:
        df = df.drop_duplicates(subset=dedup_cols)
    return df.dropna(subset=["lat", "lon"]) if "lat" in df.columns else df


# ────────────────────────────────────────────────────────────
# 3. 전역 스타일
# ────────────────────────────────────────────────────────────
st.markdown("""
<style>
.hero-banner{
    background:linear-gradient(90deg,#7F1D1D,#B91C1C);
    border-radius:14px; padding:14px 20px; margin-bottom:6px;
    display:flex; align-items:center; gap:14px;
}
.alert-badge{
    background:#fff; color:#B91C1C; font-weight:800; font-size:15px;
    padding:5px 14px; border-radius:999px; white-space:nowrap;
}
.ticker-wrap{ overflow:hidden; white-space:nowrap; flex:1; }
.ticker-text{
    display:inline-block; color:#fff; font-size:16px; font-weight:600;
    animation:ticker 45s linear infinite;
}
@keyframes ticker{ 0%{transform:translateX(100%);} 100%{transform:translateX(-100%);} }

.section-title{ font-size:24px; font-weight:800; color:#fff; margin:26px 0 10px; }
.data-period{ font-size:15px; color:#9CA3AF; margin-bottom:14px; }

.stat-card{
    background:#1F2937; border-radius:14px; padding:20px; text-align:center;
}
.stat-label{ color:#9CA3AF; font-size:15px; font-weight:600; margin-bottom:6px; }
.stat-value{ color:#fff; font-size:34px; font-weight:800; }
.stat-sub{ color:#9CA3AF; font-size:14px; margin-top:4px; }

.safety-card{
    background:#111827; border-radius:14px; padding:22px 20px; height:100%;
    box-shadow:0 4px 10px rgba(0,0,0,.15);
}
.safety-card h3{ color:#fff; font-size:21px; font-weight:800; margin-bottom:10px; }
.safety-card p{ color:#e5e7eb; font-size:16.5px; line-height:1.65; font-weight:500; }
.safety-btn a{
    display:block; text-align:center; margin-top:16px; padding:10px 0;
    background:#DC2626; color:#fff !important; font-size:16px; font-weight:700;
    border-radius:999px; text-decoration:none;
}
.safety-btn a:hover{ background:#B91C1C; }

.intensity-chip{
    display:inline-block; padding:10px 18px; margin:4px; border-radius:10px;
    font-weight:800; font-size:16px; cursor:pointer; text-decoration:none !important;
}
.legend-chip{
    padding:5px 12px; border-radius:999px; font-size:14px; font-weight:700;
    margin-right:6px; color:#fff;
}
.info-panel{ background:#1F2937; border-radius:14px; padding:20px; }
.info-item{
    background:#111827; border-radius:8px; padding:10px 14px; margin-bottom:8px;
}
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────
# 4. 데이터 로드
# ────────────────────────────────────────────────────────────
df_recent = fetch_recent_eq(days=3)
df_history = fetch_history_eq()

YEAR_MIN = int(df_history["year"].min()) if not df_history.empty else "-"
YEAR_MAX = int(df_history["year"].max()) if not df_history.empty else "-"

# ────────────────────────────────────────────────────────────
# 5. 상단 배너 (속도 완화, 중복 제거, 단일 통과)
# ────────────────────────────────────────────────────────────
recent_texts = []
if not df_recent.empty:
    for _, r in df_recent.sort_values("date", ascending=False).iterrows():
        recent_texts.append(f"{r['city']} 규모 {r['mag']} 지진 발생")
recent_texts = list(dict.fromkeys(recent_texts))  # 중복 제거
ticker_str = "   ·   ".join(recent_texts) if recent_texts else "최근 3일간 발생한 지진이 없습니다."

st.markdown(f"""
<div class="hero-banner">
    <div class="alert-badge">🔴 최근 3일 이내 발생 알림</div>
    <div class="ticker-wrap"><div class="ticker-text">{ticker_str}</div></div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"## 🌍 대한민국 지진 현황 알리미 ({YEAR_MIN}년 ~ {YEAR_MAX}년)")

# ────────────────────────────────────────────────────────────
# 6. 실시간 지진 발생 지도 (남한만, 여백을 정보 패널로 채움)
# ────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🗺️ 실시간 지진 발생 지도</div>', unsafe_allow_html=True)

map_col, info_col = st.columns([1.1, 1])

with map_col:
    m_recent = folium.Map(tiles="OpenStreetMap", dragging=True, scrollWheelZoom=True, zoom_control=True)
    m_recent.fit_bounds(KOREA_BOUNDS)
    for _, row in df_recent.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]], radius=7,
            color="#B3123B", fill=True, fill_color="#E85D8A", fill_opacity=0.9,
            popup=folium.Popup(
                f"<b>{row['city']}</b><br>규모 {row['mag']}<br>{row['date'].date() if pd.notna(row['date']) else ''}",
                max_width=250),
        ).add_to(m_recent)
    st_folium(m_recent, height=560, use_container_width=True)

with info_col:
    st.markdown(f"""
    <div class="info-panel" style="margin-bottom:14px;">
        <div class="stat-label">최근 3일 이내 발생 건수</div>
        <div class="stat-value">{len(df_recent)}건</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<p style='font-weight:800; font-size:17px; color:#fff;'>📋 최근 발생 목록</p>", unsafe_allow_html=True)
    if df_recent.empty:
        st.markdown("<div class='info-item'>최근 3일간 발생한 지진이 없습니다.</div>", unsafe_allow_html=True)
    else:
        for _, row in df_recent.sort_values("date", ascending=False).iterrows():
            st.markdown(f"""
            <div class="info-item" style="border-left:4px solid #B3123B;">
                <span style="color:#fff; font-weight:700; font-size:15.5px;">{row['city']}</span><br>
                <span style="color:#9CA3AF; font-size:13.5px;">규모 {row['mag']} · {row['date'].date() if pd.notna(row['date']) else ''}</span>
            </div>
            """, unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────
# 7. 진도 1~4단계 안내 (수동 텍스트 라벨 + 클릭 시 영상)
# ────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📊 진도(강도) 안내</div>', unsafe_allow_html=True)
chip_cols = st.columns(4)
for col, (grade, info) in zip(chip_cols, INTENSITY_LEVELS.items()):
    with col:
        st.markdown(f"""
        <a href="{info['video']}" target="_blank" class="intensity-chip"
           style="background:{intensity_color(grade)}; color:#111;">
           {info['label']}
        </a>
        <p style="color:#e5e7eb; font-size:14.5px; margin-top:8px;">{info['desc']}</p>
        """, unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────
# 8. 행동요령 (단계별 카드 + 참고영상)
# ────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🚨 지진 발생 시 행동요령</div>', unsafe_allow_html=True)
step_cols = st.columns(4)
for col, item in zip(step_cols, SAFETY_STEPS):
    with col:
        st.markdown(f"""
        <div class="safety-card">
            <h3>{item['step']}</h3>
            <p>{item['desc']}</p>
            <div class="safety-btn"><a href="{item['video']}" target="_blank">▶ 참고영상 보기</a></div>
        </div>
        """, unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────
# 9. 이력 통계 - 요약 카드
# ────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📈 역대 지진 발생 통계</div>', unsafe_allow_html=True)
st.markdown(f'<div class="data-period">📅 데이터 기준 기간 : {YEAR_MIN}년 ~ {YEAR_MAX}년</div>', unsafe_allow_html=True)

if not df_history.empty:
    total_count = len(df_history)
    max_row = df_history.loc[df_history["mag"].idxmax()]
    top_city = df_history["city"].value_counts().idxmax()
    top_city_count = df_history["city"].value_counts().max()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">전체 발생 건수</div>
            <div class="stat-value">{total_count:,}건</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        max_date = max_row['date'].date() if pd.notna(max_row['date']) else '-'
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">역대 최대 규모</div>
            <div class="stat-value">{max_row['mag']}</div>
            <div class="stat-sub">{max_row['city']} · {max_date}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">발생 최다 지역</div>
            <div class="stat-value">{top_city}</div>
            <div class="stat-sub">{top_city_count}건 발생</div>
        </div>""", unsafe_allow_html=True)

    # ── 연도별 발생건수 그래프 ──
    st.markdown('<div class="section-title" style="font-size:20px;">📆 연도별 지진 발생 건수</div>', unsafe_allow_html=True)
    yearly = df_history.groupby("year").size().reset_index(name="count")
    fig_year = px.bar(yearly, x="year", y="count", text="count")
    fig_year.update_traces(marker_color="#DC2626", textposition="outside",
                            textfont=dict(size=18, color="#111", family="Arial Black"))
    fig_year.update_layout(
        xaxis=dict(dtick=1, tickfont=dict(size=15, color="#111"), title=None),
        yaxis=dict(tickfont=dict(size=14, color="#111"), title="발생건수"),
        font=dict(size=15, color="#111"),
        plot_bgcolor="#fff", paper_bgcolor="#fff", height=430,
    )
    st.plotly_chart(fig_year, use_container_width=True)

    # ── 지역별(시·도) 발생건수 그래프 (연도별 그래프 바로 아래) ──
    st.markdown('<div class="section-title" style="font-size:20px;">📍 지역별(시·도) 지진 발생 건수</div>', unsafe_allow_html=True)
    region_count = df_history["province"].value_counts().reset_index()
    region_count.columns = ["province", "count"]
    fig_region = px.bar(region_count.sort_values("count", ascending=True),
                         x="count", y="province", orientation="h", text="count")
    fig_region.update_traces(marker_color="#B3123B", textposition="outside",
                              textfont=dict(size=17, color="#111", family="Arial Black"))
    fig_region.update_layout(
        xaxis=dict(tickfont=dict(size=14, color="#111"), title="발생건수"),
        yaxis=dict(tickfont=dict(size=16, color="#111", family="Arial Black"), title=None),
        font=dict(size=15, color="#111"),
        plot_bgcolor="#fff", paper_bgcolor="#fff", height=520,
    )
    st.plotly_chart(fig_region, use_container_width=True)

    # ── 규모별 분포 그래프 (0.5 단위) ──
    st.markdown('<div class="section-title" style="font-size:20px;">📐 규모별 지진 발생 분포</div>', unsafe_allow_html=True)
    bins = np.arange(2.0, df_history["mag"].max() + 0.5, 0.5)
    labels = [f"{b:.1f}~{b+0.4:.1f}" for b in bins[:-1]]
    df_history["mag_bin"] = pd.cut(df_history["mag"], bins=bins, labels=labels, right=False)
    mag_dist = df_history["mag_bin"].value_counts().sort_index().reset_index()
    mag_dist.columns = ["구간", "count"]
    fig_mag = px.bar(mag_dist, x="구간", y="count", text="count")
    fig_mag.update_traces(marker_color="#7C3AED", textposition="outside",
                           textfont=dict(size=17, color="#111", family="Arial Black"))
    fig_mag.update_layout(
        xaxis=dict(tickfont=dict(size=14, color="#111"), title="규모 구간"),
        yaxis=dict(tickfont=dict(size=14, color="#111"), title="발생건수"),
        font=dict(size=15, color="#111"),
        plot_bgcolor="#fff", paper_bgcolor="#fff", height=430,
    )
    st.plotly_chart(fig_mag, use_container_width=True)

    # ── 지역별 빈도 지도 + 강도 지도 (2단 배치, 남한만) ──
    st.markdown('<div class="section-title">🎯 지역별 지진 발생 빈도 · 강도 지도</div>', unsafe_allow_html=True)

    df_region_freq = df_history.groupby("city").agg(
        count=("city", "size"), lat=("lat", "mean"), lon=("lon", "mean")
    ).reset_index()
    df_region_freq["bin"] = df_region_freq["count"].apply(bin_label)
    df_region_freq["bin_color"] = df_region_freq["bin"].map(BIN_COLORS)

    freq_col, intensity_col = st.columns(2)

    with freq_col:
        st.markdown("<p style='font-weight:800; font-size:17px; color:#fff;'>🔴 발생 빈도</p>", unsafe_allow_html=True)
        legend_html = "".join(
            f"<span class='legend-chip' style='background:{c};'>{label}</span>"
            for label, c in BIN_COLORS.items()
        )
        st.markdown(legend_html, unsafe_allow_html=True)
        m_freq = folium.Map(tiles="OpenStreetMap", dragging=True, scrollWheelZoom=True, zoom_control=True)
        m_freq.fit_bounds(KOREA_BOUNDS)
        for _, row in df_region_freq.iterrows():
            folium.CircleMarker(
                location=[row["lat"], row["lon"]], radius=6,
                color=row["bin_color"], fill=True, fill_color=row["bin_color"], fill_opacity=0.85,
                popup=f"{row['city']} — {row['count']}건",
            ).add_to(m_freq)
        st_folium(m_freq, height=520, use_container_width=True)

    with intensity_col:
        st.markdown("<p style='font-weight:800; font-size:17px; color:#fff;'>🟠 발생 강도(진도)</p>", unsafe_allow_html=True)
        legend_html2 = "".join(
            f"<span class='legend-chip' style='background:{c}; color:#111; border:1px solid #ccc;'>진도 {g}</span>"
            for g, c in INTENSITY_COLORS.items() if g <= 8
        )
        st.markdown(legend_html2, unsafe_allow_html=True)
        m_intensity = folium.Map(tiles="OpenStreetMap", dragging=True, scrollWheelZoom=True, zoom_control=True)
        m_intensity.fit_bounds(KOREA_BOUNDS)
        for _, row in df_history.iterrows():
            folium.CircleMarker(
                location=[row["lat"], row["lon"]], radius=6,
                color=intensity_color(row.get("intensity")), fill=True,
                fill_color=intensity_color(row.get("intensity")), fill_opacity=0.85,
                popup=f"{row['city']} — 진도 {row.get('intensity','-')} (규모 {row['mag']})",
            ).add_to(m_intensity)
        st_folium(m_intensity, height=520, use_container_width=True)

    # ── 하단 강도 상세 지도 + TOP5 지역 패널 ──
    st.markdown('<div class="section-title">🌡️ 진도(강도) 기준 상세 지도</div>', unsafe_allow_html=True)
    bottom_map_col, bottom_info_col = st.columns([1.1, 1])

    with bottom_map_col:
        m_bottom = folium.Map(tiles="OpenStreetMap", dragging=True, scrollWheelZoom=True, zoom_control=True)
        m_bottom.fit_bounds(KOREA_BOUNDS)
        for _, row in df_history.iterrows():
            folium.CircleMarker(
                location=[row["lat"], row["lon"]], radius=6,
                color=intensity_color(row.get("intensity")), fill=True,
                fill_color=intensity_color(row.get("intensity")), fill_opacity=0.85,
                popup=f"{row['city']} — 진도 {row.get('intensity','-')} (규모 {row['mag']})",
            ).add_to(m_bottom)
        st_folium(m_bottom, height=560, use_container_width=True)

    with bottom_info_col:
        if "intensity" in df_history.columns and df_history["intensity"].notna().any():
            top_intensity = df_history.loc[df_history["intensity"].astype(float).idxmax()]
            ti_date = top_intensity["date"].date() if pd.notna(top_intensity["date"]) else "-"
            st.markdown(f"""
            <div class="info-panel" style="margin-bottom:14px;">
                <div class="stat-label">역대 최대 진도 발생</div>
                <div class="stat-value">진도 {top_intensity['intensity']} · {top_intensity['city']}</div>
                <div class="stat-sub">{ti_date} · 규모 {top_intensity['mag']}</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<p style='font-weight:800; font-size:16px; color:#fff;'>📊 진도별 발생 순위 TOP 5 지역</p>", unsafe_allow_html=True)
            top5 = df_history.groupby("city")["intensity"].max().sort_values(ascending=False).head(5)
            for city, grade in top5.items():
                st.markdown(f"""
                <div class="info-item" style="display:flex; justify-content:space-between;">
                    <span style="color:#fff; font-weight:700; font-size:15px;">{city}</span>
                    <span style="color:{intensity_color(grade)}; font-weight:800; font-size:15px;">진도 {int(grade)}</span>
                </div>
                """, unsafe_allow_html=True)
else:
    st.warning("이력 데이터를 불러오지 못했습니다. API 키 또는 네트워크 상태를 확인해 주세요.")

# ────────────────────────────────────────────────────────────
# 10. 푸터
# ────────────────────────────────────────────────────────────
st.caption(f"데이터 출처: 행정안전부 생활안전지도(safemap.go.kr), 기상청(KMA) · 조회 시각: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")

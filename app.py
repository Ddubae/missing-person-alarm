import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# ============================================================
# 기본 설정
# ============================================================
st.set_page_config(page_title="대한민국 지진 정보", page_icon="🌏", layout="wide")

SAFEMAP_KEY = "IE6DVJTK-IE6D-IE6D-IE6D-IE6DVJTKDJ"  # 실제 발급받은 키로 유지
API_URL = "https://www.safemap.go.kr/openapi2/IF_0030"

# 남한 좌표 경계 (북한 완전 제외)
SOUTH_KOREA_LAT_MIN, SOUTH_KOREA_LAT_MAX = 32.8, 38.65
SOUTH_KOREA_LON_MIN, SOUTH_KOREA_LON_MAX = 124.5, 130.0
MAP_CENTER = [35.9, 127.9]
MAP_ZOOM = 7
MAX_BOUNDS = [[32.6, 124.3], [39.0, 130.2]]
ZOOM_IN_PADDING = -60  # 남한 쪽으로 더 확대(음수 padding)

NORTH_KOREA_KEYWORDS = [
    "함경북도", "함경남도", "량강도", "양강도", "자강도",
    "평안북도", "평안남도", "황해북도", "황해남도",
    "평양", "남포", "나선", "개성", "혜산", "청진", "함흥",
    "신의주", "원산", "해주", "사리원", "강계", "육진", "북한",
]

INTENSITY_MAP_COLORS = {
    1: "#FFFFFF", 2: "#C6E6BD", 3: "#98D583", 4: "#FCE38A",
    5: "#FDBB5E", 6: "#F6842C", 7: "#E4402A", 8: "#B71C1C",
    9: "#7A0C1E", 10: "#4A0512", 11: "#2E0209", 12: "#000000",
}

# ============================================================
# 스타일
# ============================================================
st.markdown("""
<style>
.ticker-wrap {overflow:hidden; background:#B3123B; border-radius:10px; padding:12px 0; margin-bottom:18px;}
.ticker-move {display:inline-block; white-space:nowrap; animation:ticker 45s linear infinite; font-size:19px; font-weight:800; color:#fff;}
@keyframes ticker {0%{transform:translateX(100%);} 100%{transform:translateX(-100%);}}

.info-card {background:#1F2937; border-radius:14px; padding:20px; margin-bottom:14px;}
.info-card .title {color:#9CA3AF; font-size:16px; font-weight:600;}
.info-card .value {color:#fff; font-size:32px; font-weight:800; margin-top:4px;}
.info-card .caption {color:#9CA3AF; font-size:15px; margin-top:6px;}

.quake-item {background:#111827; border-left:4px solid #B3123B; border-radius:8px; padding:12px 14px; margin-bottom:8px;}
.quake-item .loc {color:#fff; font-weight:700; font-size:16px;}
.quake-item .meta {color:#9CA3AF; font-size:14px;}

.intensity-card {background:#111827; border-radius:12px; padding:16px; text-align:center; min-height:150px;}
.intensity-card .grade {font-size:22px; font-weight:800; color:#fff;}
.intensity-card .desc {font-size:17px; color:#e5e7eb; margin-top:8px; line-height:1.6;}

.safety-card {background:#111827; border-radius:14px; padding:22px; min-height:220px; box-shadow:0 4px 10px rgba(0,0,0,.15);}
.safety-card h3 {color:#fff; font-size:22px; font-weight:800; margin-bottom:10px;}
.safety-card p {color:#e5e7eb; font-size:18px; line-height:1.7;}
.safety-btn {text-align:center; margin-top:14px;}
.safety-btn a {display:inline-block; background:#B3123B; color:#fff !important; padding:10px 24px;
    border-radius:24px; font-weight:700; font-size:15px; text-decoration:none;}

.region-label {font-size:17px; font-weight:700; color:#111827; margin-bottom:6px;}
.region-search-desc {font-size:17px; color:#6B7280; line-height:1.6;}
.region-metric-card {background:#1F2937; border-radius:14px; padding:20px; text-align:center;}
.region-metric-title {font-size:16px; color:#9CA3AF; font-weight:600;}
.region-metric-value {font-size:30px; font-weight:800; color:#fff;}
.region-metric-caption {font-size:15px; color:#9CA3AF; margin-top:4px;}
.region-table th {font-size:16px !important; font-weight:700 !important; padding:10px 8px !important;}
.region-table td {font-size:16px !important; padding:9px 8px !important;}
</style>
""", unsafe_allow_html=True)

# ============================================================
# 데이터 함수
# ============================================================
def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.rename(columns={
        "occu_de": "date_raw", "occu_tm": "time_raw",
        "smints": "mag", "smints_gd": "intensity",
        "lc": "location", "lat": "lat", "lon": "lon", "objt_id": "id",
    })
    for col in ["lat", "lon", "mag"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "intensity" in df.columns:
        df["intensity"] = pd.to_numeric(df["intensity"], errors="coerce")
    if "date_raw" in df.columns:
        df["date"] = pd.to_datetime(df["date_raw"], format="%Y%m%d", errors="coerce")
    if "time_raw" in df.columns:
        df["time_str"] = df["time_raw"].astype(str).str.zfill(4)
    if "date" in df.columns and "time_str" in df.columns:
        df["datetime"] = pd.to_datetime(
            df["date"].dt.strftime("%Y-%m-%d") + " " +
            df["time_str"].str[:2] + ":" + df["time_str"].str[2:],
            errors="coerce",
        )
    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    return df


def filter_south_korea_only(df: pd.DataFrame) -> pd.DataFrame:
    """좌표 + 지명 키워드 이중 검증으로 북한 데이터를 완전히 제거"""
    if df.empty:
        return df

    def _is_south(row):
        loc = str(row.get("location", ""))
        if any(kw in loc for kw in NORTH_KOREA_KEYWORDS):
            return False
        lat, lon = row.get("lat"), row.get("lon")
        if pd.notna(lat) and pd.notna(lon):
            if not (SOUTH_KOREA_LAT_MIN <= lat <= SOUTH_KOREA_LAT_MAX and
                    SOUTH_KOREA_LON_MIN <= lon <= SOUTH_KOREA_LON_MAX):
                return False
        return True

    return df[df.apply(_is_south, axis=1)].reset_index(drop=True)


def extract_province(loc: str) -> str:
    if not isinstance(loc, str) or not loc.strip():
        return "기타"
    return loc.split()[0]


def extract_city(loc: str) -> str:
    if not isinstance(loc, str):
        return "기타"
    parts = loc.split()
    return parts[1] if len(parts) > 1 else "기타"


def intensity_color(grade) -> str:
    try:
        g = int(round(float(grade)))
    except (TypeError, ValueError):
        return "#999999"
    return INTENSITY_MAP_COLORS.get(min(max(g, 1), 12), "#999999")


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_all_eq_fast() -> pd.DataFrame:
    params = {
        "serviceKey": SAFEMAP_KEY,
        "pageNo": 1,
        "numOfRows": 3000,
        "returnType": "JSON",
    }
    res = requests.get(API_URL, params=params, timeout=15)
    res.raise_for_status()
    items = res.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])
    df = _clean_df(pd.DataFrame(items))
    df = filter_south_korea_only(df)
    df["province"] = df["location"].apply(extract_province)
    df["city"] = df["location"].apply(extract_city)
    return df


def clean_paren(text: str) -> str:
    """문자열 내 괄호와 그 안의 내용을 제거"""
    import re
    return re.sub(r"\s*\([^)]*\)", "", str(text)).strip()


# ============================================================
# 데이터 로딩
# ============================================================
with st.spinner("지진 데이터를 불러오는 중입니다..."):
    df_history = fetch_all_eq_fast()

now = datetime.now()
recent_cutoff = now - timedelta(days=3)
df_recent = df_history[df_history["datetime"] >= recent_cutoff].copy()

# ============================================================
# 1. 상단 배너 (최근 3일 알림 티커)
# ============================================================
if not df_recent.empty:
    msgs = [
        f"⚠ {r['datetime'].strftime('%m-%d %H:%M')} {clean_paren(r['location'])} 규모 {r['mag']} 지진 발생"
        for _, r in df_recent.sort_values("datetime", ascending=False).iterrows()
    ]
    ticker_text = "　　·　　".join(msgs) * 3
else:
    ticker_text = "현재 최근 3일 이내 발생한 지진 정보가 없습니다."

st.markdown(f"""
<div class="ticker-wrap">
    <div class="ticker-move">{ticker_text}</div>
</div>
""", unsafe_allow_html=True)

st.title("🌏 대한민국 지진 정보 대시보드")

# ============================================================
# 2. 실시간 지도 + 정보 패널
# ============================================================
st.markdown("### 🗺️ 실시간 지진 발생 지도")
map_col, info_col = st.columns([1.3, 1])

with map_col:
    m_recent = folium.Map(
        location=MAP_CENTER, zoom_start=MAP_ZOOM, tiles="OpenStreetMap",
        zoom_control=True, dragging=True, scrollWheelZoom=True,
        max_bounds=True, min_lat=MAX_BOUNDS[0][0], max_lat=MAX_BOUNDS[1][0],
        min_lon=MAX_BOUNDS[0][1], max_lon=MAX_BOUNDS[1][1],
    )
    m_recent.fit_bounds(MAX_BOUNDS, padding=(ZOOM_IN_PADDING, ZOOM_IN_PADDING))
    for _, row in df_recent.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]], radius=7,
            color="#B3123B", fill=True, fill_color="#E85D8A", fill_opacity=0.9,
            popup=folium.Popup(
                f"<b>{clean_paren(row['location'])}</b><br>규모 {row['mag']} / 진도 {int(row['intensity']) if pd.notna(row['intensity']) else '-'}<br>{row['datetime']}",
                max_width=250,
            ),
        ).add_to(m_recent)
    st_folium(m_recent, height=560, use_container_width=True)

with info_col:
    st.markdown(f"""
    <div class="info-card">
        <div class="title">최근 3일 이내 발생 건수</div>
        <div class="value">{len(df_recent)}건</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<p class='region-label'>📋 최근 발생 목록</p>", unsafe_allow_html=True)
    if df_recent.empty:
        st.markdown("<p style='color:#9CA3AF;'>최근 3일간 발생한 지진이 없습니다.</p>", unsafe_allow_html=True)
    else:
        for _, row in df_recent.sort_values("datetime", ascending=False).iterrows():
            st.markdown(f"""
            <div class="quake-item">
                <div class="loc">{clean_paren(row['location'])}</div>
                <div class="meta">규모 {row['mag']} · 진도 {int(row['intensity']) if pd.notna(row['intensity']) else '-'} · {row['datetime']}</div>
            </div>
            """, unsafe_allow_html=True)

# ============================================================
# 3. 진도 단계 안내
# ============================================================
st.markdown("### 📶 진도(계기 진도) 단계 안내")
INTENSITY_GUIDE = [
    {"grade": "Ⅰ", "desc": "거의 느낄 수 없음", "video": "https://www.youtube.com/watch?v=zO2H4dzGsho"},
    {"grade": "Ⅱ~Ⅲ", "desc": "실내에서 약하게 느낌", "video": "https://www.youtube.com/watch?v=zO2H4dzGsho"},
    {"grade": "Ⅳ~Ⅴ", "desc": "물건이 흔들리고 소리가 남", "video": "https://www.youtube.com/watch?v=zO2H4dzGsho"},
    {"grade": "Ⅵ 이상", "desc": "구조물 손상 위험, 대피 필요", "video": "https://www.youtube.com/watch?v=zO2H4dzGsho"},
]
cols = st.columns(4)
for col, item in zip(cols, INTENSITY_GUIDE):
    with col:
        st.markdown(f"""
        <div class="intensity-card">
            <div class="grade">진도 {item['grade']}</div>
            <div class="desc">{item['desc']}</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(f"<div class='safety-btn'><a href='{item['video']}' target='_blank'>▶ 참고영상 보기</a></div>", unsafe_allow_html=True)

# ============================================================
# 4. 행동요령 4단계
# ============================================================
st.markdown("### 🛟 지진 발생 시 행동요령")
SAFETY_STEPS = [
    {"step": "1단계. 평소 대비", "desc": "가구 고정, 대피 경로 확인, 비상용품 준비", "video": "https://www.youtube.com/watch?v=zO2H4dzGsho"},
    {"step": "2단계. 흔들릴 때", "desc": "책상 아래로 몸을 피하고 머리를 보호", "video": "https://www.youtube.com/watch?v=zO2H4dzGsho"},
    {"step": "3단계. 흔들림이 멈춘 후", "desc": "가스와 전기를 차단하고 계단으로 대피", "video": "https://www.youtube.com/watch?v=zO2H4dzGsho"},
    {"step": "4단계. 대피 후", "desc": "안전한 장소에서 공식 안내에 따라 행동", "video": "https://www.youtube.com/watch?v=zO2H4dzGsho"},
]
cols = st.columns(4)
for col, item in zip(cols, SAFETY_STEPS):
    with col:
        st.markdown(f"""
        <div class="safety-card">
            <h3>{item['step']}</h3>
            <p>{item['desc']}</p>
            <div class="safety-btn"><a href="{item['video']}" target="_blank">▶ 참고영상 보기</a></div>
        </div>
        """, unsafe_allow_html=True)

# ============================================================
# 5. 이력 통계
# ============================================================
st.markdown("### 📊 지진 이력 통계")
stat_col1, stat_col2, stat_col3 = st.columns(3)

with stat_col1:
    st.markdown(f"""
    <div class="info-card">
        <div class="title">전체 발생 건수</div>
        <div class="value">{len(df_history):,}건</div>
        <div class="caption">{df_history['date'].min().year}년 ~ {df_history['date'].max().year}년</div>
    </div>
    """, unsafe_allow_html=True)

with stat_col2:
    top = df_history.sort_values("mag", ascending=False).iloc[0]
    st.markdown(f"""
    <div class="info-card">
        <div class="title">역대 최대 규모</div>
        <div class="value">규모 {top['mag']}</div>
        <div class="caption">{clean_paren(top['location'])} · {top['date'].strftime('%Y-%m-%d')}</div>
    </div>
    """, unsafe_allow_html=True)

with stat_col3:
    top_region = df_history.groupby("city").size().sort_values(ascending=False)
    st.markdown(f"""
    <div class="info-card">
        <div class="title">최다 발생 지역</div>
        <div class="value">{top_region.index[0]}</div>
        <div class="caption">{top_region.iloc[0]}건 발생</div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# 6. 연도별 발생 건수
# ============================================================
st.markdown("#### 📆 연도별 지진 발생 건수")
yearly = df_history.groupby(df_history["date"].dt.year).size().reset_index()
yearly.columns = ["year", "count"]
fig_year = px.bar(yearly, x="year", y="count", text="count")
fig_year.update_traces(marker_color="#B3123B", textposition="outside",
                        textfont=dict(size=16, color="#111827"))
fig_year.update_layout(
    xaxis=dict(dtick=1, tickfont=dict(size=15)),
    yaxis=dict(title="발생 건수", tickfont=dict(size=15)),
    font=dict(size=15), height=420, margin=dict(t=20, b=20),
)
st.plotly_chart(fig_year, use_container_width=True)

# ============================================================
# 7. 지역별 TOP 15
# ============================================================
st.markdown("#### 지역별(도·시 단위) 지진 발생 건수 TOP 15")
region_count = df_history.groupby("city").size().sort_values(ascending=False).head(15).reset_index()
region_count.columns = ["city", "count"]
fig_region = px.bar(region_count.sort_values("count"), x="count", y="city", orientation="h", text="count")
fig_region.update_traces(marker_color="#E4402A", textposition="outside",
                          textfont=dict(size=16, color="#111827"))
fig_region.update_layout(
    xaxis=dict(title="발생 건수", tickfont=dict(size=15)),
    yaxis=dict(title="", tickfont=dict(size=17, family="Arial Black")),
    font=dict(size=15), height=520, margin=dict(t=20, b=20, l=10),
)
st.plotly_chart(fig_region, use_container_width=True)

# ============================================================
# 8. 규모별 분포
# ============================================================
st.markdown("#### 📈 규모별 발생 분포")
mag_bins = np.arange(df_history["mag"].min() // 0.5 * 0.5, df_history["mag"].max() + 0.5, 0.5)
df_history["mag_bin"] = pd.cut(df_history["mag"], bins=mag_bins)
mag_dist = df_history["mag_bin"].value_counts().sort_index().reset_index()
mag_dist.columns = ["범위", "건수"]
mag_dist["범위"] = mag_dist["범위"].astype(str)
fig_mag = px.bar(mag_dist, x="범위", y="건수", text="건수")
fig_mag.update_traces(marker_color="#0EA5E9", textposition="outside",
                       textfont=dict(size=15, color="#111827"))
fig_mag.update_layout(font=dict(size=14), height=400, margin=dict(t=20, b=20))
st.plotly_chart(fig_mag, use_container_width=True)

# ============================================================
# 9. 발생 빈도 지도 / 진도 지도 (2열)
# ============================================================
st.markdown("### 🎯 지역별 지진 발생 빈도 · 강도 지도")
freq_col, intensity_col = st.columns(2)

with freq_col:
    st.markdown("<p class='region-label'>🔴 발생 빈도</p>", unsafe_allow_html=True)
    m_freq = folium.Map(location=MAP_CENTER, zoom_start=MAP_ZOOM, tiles="OpenStreetMap")
    m_freq.fit_bounds(MAX_BOUNDS, padding=(ZOOM_IN_PADDING, ZOOM_IN_PADDING))
    city_counts = df_history.groupby(["city", "lat", "lon"]).size().reset_index(name="count")
    max_count = city_counts["count"].max()
    for _, row in city_counts.iterrows():
        ratio = row["count"] / max_count
        folium.CircleMarker(
            location=[row["lat"], row["lon"]], radius=5 + ratio * 15,
            color="#B3123B", fill=True, fill_color="#B3123B", fill_opacity=0.6,
            popup=f"{row['city']} — {row['count']}건",
        ).add_to(m_freq)
    st_folium(m_freq, height=520, use_container_width=True)

with intensity_col:
    st.markdown("<p class='region-label'>🟠 발생 강도(진도)</p>", unsafe_allow_html=True)
    m_int = folium.Map(location=MAP_CENTER, zoom_start=MAP_ZOOM, tiles="OpenStreetMap")
    m_int.fit_bounds(MAX_BOUNDS, padding=(ZOOM_IN_PADDING, ZOOM_IN_PADDING))
    for _, row in df_history.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]], radius=6,
            color=intensity_color(row["intensity"]), fill=True,
            fill_color=intensity_color(row["intensity"]), fill_opacity=0.85,
            popup=f"{row['city']} — 진도 {row['intensity']} (규모 {row['mag']})",
        ).add_to(m_int)
    st_folium(m_int, height=520, use_container_width=True)

# ============================================================
# 10. 상세 진도 지도 + TOP5
# ============================================================
st.markdown("### 🌡️ 진도(강도) 기준 상세 지도")
bottom_map_col, bottom_info_col = st.columns([1.3, 1])

with bottom_map_col:
    m_bottom = folium.Map(location=MAP_CENTER, zoom_start=MAP_ZOOM, tiles="OpenStreetMap")
    m_bottom.fit_bounds(MAX_BOUNDS, padding=(ZOOM_IN_PADDING, ZOOM_IN_PADDING))
    for _, row in df_history.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]], radius=6,
            color=intensity_color(row["intensity"]), fill=True,
            fill_color=intensity_color(row["intensity"]), fill_opacity=0.85,
            popup=f"{row['city']} — 진도 {row['intensity']} (규모 {row['mag']})",
        ).add_to(m_bottom)
    st_folium(m_bottom, height=560, use_container_width=True)

with bottom_info_col:
    top_i = df_history.sort_values("intensity", ascending=False).iloc[0]
    st.markdown(f"""
    <div class="info-card">
        <div class="title">역대 최대 진도 발생</div>
        <div class="value">진도 {int(top_i['intensity'])} · {top_i['city']}</div>
        <div class="caption">{top_i['date'].strftime('%Y-%m-%d')} · 규모 {top_i['mag']}</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<p class='region-label'>📊 진도별 발생 순위 TOP 5 지역</p>", unsafe_allow_html=True)
    top5 = df_history.groupby("city")["intensity"].max().sort_values(ascending=False).head(5)
    for city, grade in top5.items():
        st.markdown(f"""
        <div class="quake-item" style="display:flex; justify-content:space-between; align-items:center;">
            <span class="loc">{city}</span>
            <span style="color:{intensity_color(grade)}; font-weight:800; font-size:17px;">진도 {int(grade)}</span>
        </div>
        """, unsafe_allow_html=True)

# ============================================================
# 11. 내 지역 지진 발생기록 찾기
# ============================================================
st.markdown("---")
st.markdown("### 🔍 내 지역 지진 발생기록 찾기")
st.markdown("<p class='region-search-desc'>실제 관측 데이터를 기반으로 원하는 시·도와 시·군·구를 선택하면, 해당 지역에서 발생한 모든 지진의 강도·빈도·날짜를 한눈에 조회할 수 있습니다.</p>", unsafe_allow_html=True)

col_sido, col_sigungu = st.columns(2)
sido_list = sorted(df_history["province"].dropna().unique().tolist())

with col_sido:
    st.markdown("<p class='region-label'>① 시·도 선택</p>", unsafe_allow_html=True)
    sido_selected = st.selectbox("", sido_list, key="sido_select", label_visibility="collapsed")

sigungu_list = sorted(df_history[df_history["province"] == sido_selected]["city"].dropna().unique().tolist())

with col_sigungu:
    st.markdown("<p class='region-label'>② 시·군·구 선택</p>", unsafe_allow_html=True)
    sigungu_selected = st.selectbox("", sigungu_list, key="sigungu_select", label_visibility="collapsed")

df_region = df_history[
    (df_history["province"] == sido_selected) & (df_history["city"] == sigungu_selected)
].sort_values("datetime", ascending=False)

r1, r2, r3 = st.columns(3)
with r1:
    st.markdown(f"""
    <div class="region-metric-card">
        <div class="region-metric-title">총 발생 건수</div>
        <div class="region-metric-value">{len(df_region)}건</div>
    </div>
    """, unsafe_allow_html=True)

with r2:
    if not df_region.empty:
        max_row = df_region.sort_values("mag", ascending=False).iloc[0]
        st.markdown(f"""
        <div class="region-metric-card">
            <div class="region-metric-title">최대 규모</div>
            <div class="region-metric-value">규모 {max_row['mag']}</div>
            <div class="region-metric-caption">{max_row['date'].strftime('%Y-%m-%d')}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="region-metric-card">
            <div class="region-metric-title">최대 규모</div>
            <div class="region-metric-value">-</div>
        </div>
        """, unsafe_allow_html=True)

with r3:
    if not df_region.empty:
        recent_row = df_region.iloc[0]
        st.markdown(f"""
        <div class="region-metric-card">
            <div class="region-metric-title">최근 발생</div>
            <div class="region-metric-value">{recent_row['date'].strftime('%Y-%m-%d')}</div>
            <div class="region-metric-caption">규모 {recent_row['mag']} · 진도 {int(recent_row['intensity']) if pd.notna(recent_row['intensity']) else '-'}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="region-metric-card">
            <div class="region-metric-title">최근 발생</div>
            <div class="region-metric-value">기록 없음</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown(f"<p class='region-label'>📋 {sido_selected} {sigungu_selected} 전체 발생 이력</p>", unsafe_allow_html=True)

if df_region.empty:
    st.markdown("<p style='color:#6B7280; font-size:16px;'>해당 지역에서 관측된 지진 기록이 없습니다.</p>", unsafe_allow_html=True)
else:
    table_df = df_region[["date", "location", "mag", "intensity"]].copy()
    table_df["date"] = table_df["date"].dt.strftime("%Y-%m-%d")
    table_df["location"] = table_df["location"].apply(clean_paren)
    table_df["intensity"] = table_df["intensity"].apply(lambda x: int(x) if pd.notna(x) else "-")
    table_df.columns = ["발생일", "발생 위치", "규모", "진도"]

    styled = (
        table_df.style
        .set_properties(**{"font-size": "16px", "padding": "8px", "text-align": "center"})
        .set_table_styles([
            {"selector": "th", "props": [("font-size", "16px"), ("font-weight", "700"),
                                          ("background-color", "#1F2937"), ("color", "#fff")]},
        ])
        .hide(axis="index")
    )
    st.write(styled.to_html(), unsafe_allow_html=True)

# ============================================================
# 12. 푸터
# ============================================================
st.markdown("---")
st.markdown(f"""
<p style="color:#9CA3AF; font-size:14px; text-align:center;">
데이터 출처: 행정안전부 생활안전지도 OpenAPI (SafeMap) · 조회 시각: {now.strftime('%Y-%m-%d %H:%M')}
</p>
""", unsafe_allow_html=True)

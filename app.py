import re
import json
import math
from datetime import datetime, timedelta

import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import streamlit as st

# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(page_title="대한민국 지진 현황 알리미", layout="wide", page_icon="🌍")

# 실제 서비스에서는 st.secrets["KMA_KEY"] / st.secrets["SAFEMAP_KEY"] 로 옮기는 것을 권장합니다.
KMA_KEY = "69bb08cc0eacf8cbdfffc6b9b4ecf242d33a1cc5955004d3048de6fb54c985df"
SAFEMAP_KEY = "IE6DVJTK-IE6D-IE6D-IE6D-IE6DVJTKDJ"

KMA_URL = "https://apis.data.go.kr/1360000/EqkInfoService/getEqkMsg"
SAFEMAP_URL = "https://www.safemap.go.kr/openapi2/IF_0030"

PROVINCE_CENTER = {
    "서울": (37.5665, 126.9780), "경기": (37.4138, 127.5183), "인천": (37.4563, 126.7052),
    "강원": (37.8228, 128.1555), "충북": (36.8000, 127.7000), "충남": (36.5184, 126.8000),
    "대전": (36.3504, 127.3845), "세종": (36.4800, 127.2890), "전북": (35.7175, 127.1530),
    "전남": (34.8161, 126.4630), "광주": (35.1595, 126.8526), "경북": (36.4919, 128.8889),
    "경남": (35.4606, 128.2132), "대구": (35.8714, 128.6014), "울산": (35.5384, 129.3114),
    "부산": (35.1796, 129.0756), "제주": (33.4996, 126.5312),
}

BIN_COLORS = {
    "0~10건": "#F5B7C4",
    "11~50건": "#E85D8A",
    "51~100건": "#B3123B",
    "100건 초과": "#5C0A22",
}

INTENSITY_LEVELS = [
    {"key": "1_2", "label": "진도 Ⅰ~Ⅱ", "desc": "거의 느낄 수 없음",
     "detail": "특별히 좋은 조건에서 극소수만 느끼며, 대부분 지진계에만 기록되는 수준입니다.",
     "color": "#8E8E93",
     "video": "https://www.youtube.com/embed/2tt1wRGJY8c"},
    {"key": "3_4", "label": "진도 Ⅲ~Ⅳ", "desc": "약한 흔들림",
     "detail": "실내에 있는 사람 다수가 흔들림을 느끼며, 매달린 물체가 흔들릴 수 있습니다.",
     "color": "#E8A93A",
     "video": "https://www.youtube.com/embed/oNTGC34kZtU"},
    {"key": "5_6", "label": "진도 Ⅴ~Ⅵ", "desc": "뚜렷한 흔들림",
     "detail": "거의 모든 사람이 느끼고, 놀라서 밖으로 대피하는 사람이 생기며 물건이 넘어질 수 있습니다.",
     "color": "#D9534F",
     "video": "https://www.youtube.com/embed/8LUG9Iuk8rI"},
    {"key": "7_8", "label": "진도 Ⅶ~Ⅷ", "desc": "구조물 피해 시작",
     "detail": "내진설계가 부실한 건물에 균열·붕괴가 시작되고, 서있기 힘들 정도의 흔들림입니다.",
     "color": "#B3123B",
     "video": "https://www.youtube.com/embed/2tt1wRGJY8c"},
    {"key": "9_up", "label": "진도 Ⅸ 이상", "desc": "심각한 붕괴",
     "detail": "내진 여부와 관계없이 건물 붕괴가 발생할 수 있는 매우 위험한 수준입니다.",
     "color": "#5C0A22",
     "video": "https://www.youtube.com/embed/oNTGC34kZtU"},
]

# =========================================================
# 스타일 (글자 크게, 색상 진하게)
# =========================================================
st.markdown("""
<style>
html, body, [class*="css"]  { font-size: 18px !important; }
.hero-box {
    background: linear-gradient(90deg,#1a1a2e,#8B0000);
    padding: 22px 28px; border-radius: 10px; color: white; margin-bottom: 6px;
}
.hero-title { font-size: 30px; font-weight: 800; margin: 0; }
.hero-sub { font-size: 16px; opacity: 0.9; margin-top: 4px; }

.ticker-wrap {
    background: #7a0f24; overflow: hidden; white-space: nowrap;
    border-radius: 0 0 10px 10px; padding: 10px 0; margin-bottom: 22px;
}
.ticker-static {
    display: flex; justify-content: center; gap: 40px; color: #fff;
    font-size: 20px; font-weight: 700; flex-wrap: wrap;
}
.ticker-move {
    display: inline-block; white-space: nowrap; color: #fff;
    font-size: 20px; font-weight: 700;
    animation: ticker 22s linear infinite;
}
@keyframes ticker { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }

.section-title { font-size: 24px; font-weight: 800; border-left: 6px solid #B3123B;
    padding-left: 12px; margin: 30px 0 14px 0; }

.data-range { font-size: 18px; font-weight: 700; color: #444; margin-bottom: 14px; }

.legend-chip { display:inline-block; padding:6px 14px; border-radius: 20px; color:#fff;
    font-size: 16px; font-weight: 700; margin-right: 10px; }

.stat-card { background:#fafafa; border:1px solid #eee; border-radius: 12px; padding: 20px;
    text-align:center; }
.stat-num { font-size: 34px; font-weight: 900; color:#B3123B; }
.stat-label { font-size: 16px; color:#666; margin-top: 6px; }

.level-card { border-radius: 10px; padding: 16px; text-align:center; color:white;
    font-weight: 800; font-size: 20px; cursor:pointer; }
.level-sub { font-size: 15px; font-weight: 500; margin-top: 4px; }

.close-btn button { background:#444 !important; color:#fff !important; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 데이터 로딩
# =========================================================
@st.cache_data(ttl=180)
def fetch_recent_eq():
    today = datetime.now()
    frm = (today - timedelta(days=2)).strftime("%Y%m%d")
    to = today.strftime("%Y%m%d")
    params = {"ServiceKey": KMA_KEY, "pageNo": 1, "numOfRows": 50,
              "dataType": "JSON", "fromTmFc": frm, "toTmFc": to}
    try:
        r = requests.get(KMA_URL, params=params, timeout=10)
        data = r.json()
        items = data.get("response", {}).get("body", {}).get("items", {})
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]
        return pd.DataFrame(items) if items else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=6 * 3600)
def fetch_history_eq():
    all_rows = []
    page = 1
    total = None
    while True:
        params = {"serviceKey": SAFEMAP_KEY, "pageNo": page, "numOfRows": 700, "returnType": "JSON"}
        try:
            r = requests.get(SAFEMAP_URL, params=params, timeout=15)
            data = r.json()
        except Exception:
            break
        body = data.get("response", {}) if isinstance(data, dict) else {}
        result = body.get("body", body) if body else data
        items = result.get("items", []) if isinstance(result, dict) else []
        if not items:
            break
        all_rows.extend(items)
        total = result.get("totalCount", len(all_rows))
        if len(all_rows) >= int(total):
            break
        page += 1
        if page > 10:
            break
    return pd.DataFrame(all_rows)


def extract_province(text):
    if not isinstance(text, str):
        return "기타"
    for key in PROVINCE_CENTER.keys():
        if text.startswith(key) or key in text[:6]:
            return key
    return "기타"


def extract_city(text):
    if not isinstance(text, str):
        return "기타"
    m = re.search(r'([가-힣]{2,6}시)', text)
    if m:
        return m.group(1)
    m = re.search(r'([가-힣]{2,6}군)', text)
    if m:
        return m.group(1)
    m = re.search(r'([가-힣]{2,6}구)', text)
    if m:
        return m.group(1)
    return text[:6] if text else "기타"


def bin_label(cnt):
    if cnt <= 10:
        return "0~10건"
    elif cnt <= 50:
        return "11~50건"
    elif cnt <= 100:
        return "51~100건"
    else:
        return "100건 초과"


def mag_color(mag):
    try:
        mag = float(mag)
    except Exception:
        return "#999999"
    if mag < 3.0:
        return "#9E9E9E"
    elif mag < 4.0:
        return "#E8D96A"
    elif mag < 5.0:
        return "#E8A93A"
    else:
        return "#B3123B"


recent_df = fetch_recent_eq()
history_df = fetch_history_eq()

# 최근 데이터 전처리
recent_list = []
if not recent_df.empty:
    for _, row in recent_df.iterrows():
        recent_list.append({
            "time": str(row.get("tmEqk", "")),
            "loc": row.get("loc", "-"),
            "mt": row.get("mt", "-"),
            "lat": row.get("lat"),
            "lon": row.get("lon"),
            "inT": row.get("inT", "-"),
        })

# 중복 제거 (동일 시각+위치+규모)
seen = set()
unique_recent = []
for item in recent_list:
    key = (item["time"], item["loc"], item["mt"])
    if key not in seen:
        seen.add(key)
        unique_recent.append(item)

# 역사 데이터 전처리
if not history_df.empty:
    history_df = history_df.copy()
    history_df["mt"] = pd.to_numeric(history_df.get("smints", history_df.get("mt")), errors="coerce")
    history_df["loc_text"] = history_df.get("lc", history_df.get("loc", ""))
    history_df["lat"] = pd.to_numeric(history_df.get("lat"), errors="coerce")
    history_df["lon"] = pd.to_numeric(history_df.get("lon"), errors="coerce")
    date_col = history_df.get("occu_de", history_df.get("tmEqk"))
    history_df["date_str"] = date_col.astype(str)
    history_df["year"] = history_df["date_str"].str[:4]
    history_df["province"] = history_df["loc_text"].apply(extract_province)
    history_df["city"] = history_df["loc_text"].apply(extract_city)
    history_df = history_df.dropna(subset=["lat", "lon"])

# =========================================================
# 상단 배너 + 속보 티커
# =========================================================
st.markdown("""
<div class="hero-box">
  <div class="hero-title">🔴 대한민국 지진 현황 알리미</div>
  <div class="hero-sub">기상청·행정안전부 공식 데이터를 기반으로 실시간 지진 속보와 최근 이력을 보여드립니다.</div>
</div>
""", unsafe_allow_html=True)

if not unique_recent:
    ticker_html = '<div class="ticker-static">현재 최근 3일 이내 발생한 지진 속보가 없습니다.</div>'
else:
    def fmt_item(it):
        t = it["time"]
        t_disp = f"{t[:4]}.{t[4:6]}.{t[6:8]} {t[8:10]}:{t[10:12]}" if len(t) >= 12 else t
        return f'🔴 {t_disp} · 규모 {it["mt"]} · {it["loc"]}'

    items_txt = [fmt_item(it) for it in unique_recent]
    if len(items_txt) < 4:
        joined = "&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;".join(items_txt)
        ticker_html = f'<div class="ticker-static">{joined}</div>'
    else:
        joined = "&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;".join(items_txt)
        ticker_html = f'<div class="ticker-move">{joined}&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;{joined}</div>'

st.markdown(f'<div class="ticker-wrap">{ticker_html}</div>', unsafe_allow_html=True)

# =========================================================
# 실시간 지진 발생 지도 (최근 3일)
# =========================================================
st.markdown('<div class="section-title">🗺️ 실시간 지진 발생 지도 (최근 3일)</div>', unsafe_allow_html=True)

m_recent = folium.Map(location=[36.3, 127.8], zoom_start=7, tiles="OpenStreetMap",
                       zoom_control=False, scrollWheelZoom=False, dragging=False,
                       doubleClickZoom=False, touchZoom=False)

if unique_recent:
    for it in unique_recent:
        if it["lat"] is None or it["lon"] is None:
            continue
        popup_html = f"""
        <div style='font-size:15px; line-height:1.6;'>
        <b>📍 진원지 :</b> {it['loc']}<br>
        <b>강도(규모) :</b> {it['mt']}<br>
        <b>진도 :</b> {it['inT']}
        </div>
        """
        folium.CircleMarker(
            location=[float(it["lat"]), float(it["lon"])],
            radius=9, color="#D9534F", fill=True, fill_color="#D9534F", fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{it['loc']} · 규모 {it['mt']}"
        ).add_to(m_recent)

st_folium(m_recent, width=None, height=480, returned_objects=[])

# =========================================================
# 진도별 설명 + 영상
# =========================================================
st.markdown('<div class="section-title">📺 지진 규모와 진도, 클릭해서 실제 피해 영상을 확인하세요</div>', unsafe_allow_html=True)

if "selected_level" not in st.session_state:
    st.session_state.selected_level = None

cols = st.columns(len(INTENSITY_LEVELS))
for col, lvl in zip(cols, INTENSITY_LEVELS):
    with col:
        st.markdown(f"""
        <div class="level-card" style="background:{lvl['color']};">
        {lvl['label']}
        <div class="level-sub">{lvl['desc']}</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("▶ 영상보기", key=f"btn_{lvl['key']}"):
            st.session_state.selected_level = lvl["key"]
            st.rerun()

if st.session_state.selected_level:
    lvl = next(l for l in INTENSITY_LEVELS if l["key"] == st.session_state.selected_level)
    st.markdown(f"### 🎬 {lvl['label']} — {lvl['desc']}")
    st.markdown(f"<p style='font-size:18px;'>{lvl['detail']}</p>", unsafe_allow_html=True)
    st.video(lvl["video"])
    if st.button("✕ 영상 닫기", key="close_video"):
        st.session_state.selected_level = None
        st.rerun()

# =========================================================
# 안전 행동 카드
# =========================================================
st.markdown('<div class="section-title">🛡️ 지진 발생 시 행동 요령</div>', unsafe_allow_html=True)
safety_steps = [
    ("1. 평소 대비", "가구나 물건이 넘어지지 않도록 고정하고, 가족과 대피 장소를 미리 정해둡니다."),
    ("2. 흔들리는 동안", "탁자 아래로 몸을 숨기고 흔들림이 멈출 때까지 기다립니다."),
    ("3. 흔들림이 멈추면", "전기·가스를 차단하고 신발을 신은 채 신속하게 대피합니다."),
    ("4. 장소별 대응", "엘리베이터 대신 계단을 이용하고, 운동장 등 넓은 공간에서 대기합니다."),
]
cols = st.columns(4)
for col, (title, desc) in zip(cols, safety_steps):
    with col:
        st.markdown(f"""
        <div style='background:#f5f5f5; border-radius:10px; padding:18px; height:150px;'>
        <b style='font-size:18px;'>{title}</b>
        <p style='font-size:16px; margin-top:8px;'>{desc}</p>
        </div>
        """, unsafe_allow_html=True)

# =========================================================
# 10년 통계
# =========================================================
st.markdown('<div class="section-title">📊 지진 발생 이력 통계</div>', unsafe_allow_html=True)

if not history_df.empty:
    years_sorted = sorted(history_df["year"].dropna().unique())
    start_y, end_y = years_sorted[0], years_sorted[-1]
    st.markdown(f'<div class="data-range">데이터 기준 기간 : {start_y}년 1월 ~ {end_y}년 9월 (행정안전부 생활안전지도, 규모 2.0 이상 기준)</div>', unsafe_allow_html=True)

    total_cnt = len(history_df)
    max_row = history_df.loc[history_df["mt"].idxmax()]
    city_counts = history_df["city"].value_counts()
    top_city = city_counts.index[0]
    top_city_cnt = city_counts.iloc[0]
    top_city_pct = round(top_city_cnt / total_cnt * 100, 1)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""<div class="stat-card"><div class="stat-num">{total_cnt:,}건</div>
        <div class="stat-label">등록된 전체 지진 건수</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="stat-card"><div class="stat-num">규모 {max_row['mt']}</div>
        <div class="stat-label">역대 최대 규모<br>{max_row['loc_text']}</div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="stat-card"><div class="stat-num">{top_city} {top_city_cnt}건</div>
        <div class="stat-label">발생 최다 지역 (시 단위)<br>전체의 {top_city_pct}%</div></div>""", unsafe_allow_html=True)

    st.write("")

    # 연도별 그래프 (이상치 강조)
    yearly = history_df.groupby("year").size().reset_index(name="cnt")
    mean_v, std_v = yearly["cnt"].mean(), yearly["cnt"].std()
    yearly["color"] = yearly["cnt"].apply(lambda x: "#B3123B" if x > mean_v + std_v else "#B0B0B0")

    fig_year = go.Figure(go.Bar(
        x=yearly["year"], y=yearly["cnt"], marker_color=yearly["color"],
        text=[f"{v}건" for v in yearly["cnt"]], textposition="outside",
        textfont=dict(size=16)
    ))
    fig_year.update_layout(
        title=f"연도별 지진 발생 건수 ({start_y}년 1월 ~ {end_y}년 9월)",
        font=dict(size=16), height=420, margin=dict(t=60, b=40)
    )
    st.plotly_chart(fig_year, use_container_width=True)

    # 규모 분포
    fig_mag = px.histogram(history_df, x="mt", nbins=20, title="규모별 발생 분포")
    fig_mag.update_traces(marker_color="#B3123B")
    fig_mag.update_layout(font=dict(size=16), height=380)
    st.plotly_chart(fig_mag, use_container_width=True)

    # =========================================================
    # 지역별 발생 빈도 지도 (작은 점, 균일 크기)
    # =========================================================
    st.markdown('<div class="section-title">🎯 지역별 지진 발생 빈도</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="data-range">데이터 기준 기간 : {start_y}년 1월 ~ {end_y}년 9월</div>', unsafe_allow_html=True)

    legend_html = "".join([
        f'<span class="legend-chip" style="background:{c};">{label}</span>'
        for label, c in BIN_COLORS.items()
    ])
    st.markdown(legend_html, unsafe_allow_html=True)
    st.write("")

    province_counts = history_df["province"].value_counts().to_dict()

    m_freq = folium.Map(location=[36.3, 127.8], zoom_start=7, tiles="OpenStreetMap",
                         zoom_control=False, scrollWheelZoom=False, dragging=False,
                         doubleClickZoom=False, touchZoom=False)

    for _, row in history_df.iterrows():
        prov = row["province"]
        cnt = province_counts.get(prov, 0)
        label = bin_label(cnt)
        color = BIN_COLORS[label]
        popup_html = f"""
        <div style='font-size:14px; line-height:1.6;'>
        <b>📍 진원지 :</b> {row['loc_text']}<br>
        <b>강도(규모) :</b> {row['mt']}<br>
        <b>{prov} 누적 발생 :</b> {cnt}건 ({label})
        </div>
        """
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=3, color=color, fill=True, fill_color=color, fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=260),
        ).add_to(m_freq)

    st_folium(m_freq, width=None, height=520, returned_objects=[])

    # 지역별(시 단위) 발생건수 막대그래프
    city_top = city_counts.head(15).reset_index()
    city_top.columns = ["city", "cnt"]
    city_top["color"] = city_top["cnt"].apply(
        lambda x: "#B3123B" if x == city_top["cnt"].max() else "#B0B0B0"
    )

    fig_city = go.Figure(go.Bar(
        x=city_top["city"], y=city_top["cnt"], marker_color=city_top["color"],
        text=[f"{v}건" for v in city_top["cnt"]], textposition="outside",
        textfont=dict(size=16)
    ))
    fig_city.update_layout(
        title="지역별(시 단위) 지진 발생 건수 TOP 15",
        font=dict(size=16), height=440, margin=dict(t=60, b=80)
    )
    fig_city.update_xaxes(tickangle=-30)
    st.plotly_chart(fig_city, use_container_width=True)

else:
    st.warning("이력 데이터를 불러오지 못했습니다. API 키 또는 네트워크 상태를 확인해주세요.")

st.markdown("---")
st.caption(f"※ 데이터 출처 : 기상청 지진정보(EqkInfoService), 행정안전부 생활안전지도(safemap.go.kr) · "
            f"조회 시각 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

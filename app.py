import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import json
from datetime import datetime, timedelta

st.set_page_config(page_title="대한민국 지진 현황 알리미", page_icon="🌍", layout="wide")

# ── 인증키 및 API 상수 ──
KMA_KEY = "69bb08cc0eacf8cbdfffc6b9b4ecf242d33a1cc5955004d3048de6fb54c985df"
KMA_URL = "https://apis.data.go.kr/1360000/EqkInfoService/getEqkMsg"
SAFEMAP_KEY = "IE6DVJTK-IE6D-IE6D-IE6D-IE6DVJTKDJ"
SAFEMAP_URL = "https://www.safemap.go.kr/openapi2/IF_0030"

PROVINCE_CENTER = {
    "서울": (37.5665, 126.9780), "부산": (35.1796, 129.0756), "대구": (35.8714, 128.6014),
    "인천": (37.4563, 126.7052), "광주": (35.1595, 126.8526), "대전": (36.3504, 127.3845),
    "울산": (35.5384, 129.3114), "세종": (36.4801, 127.2890), "경기": (37.4138, 127.5183),
    "강원": (37.8228, 128.1555), "충북": (36.6357, 127.4917), "충남": (36.5184, 126.8000),
    "전북": (35.7175, 127.1530), "전남": (34.8679, 126.9910), "경북": (36.4919, 128.8889),
    "경남": (35.4606, 128.2132), "제주": (33.4996, 126.5312),
}

BIN_COLORS_RGB = {
    "0~10건":   [255, 193, 208, 200],
    "11~50건":  [255, 111, 145, 220],
    "51~100건": [224, 30, 90, 235],
    "100건 초과": [122, 0, 50, 255],
}
BIN_COLORS_HEX = {
    "0~10건": "#FFC1D0", "11~50건": "#FF6F91", "51~100건": "#E01E5A", "100건 초과": "#7A0032",
}

INTENSITY_LEVELS = [
    {"key": "low", "range": "진도 Ⅰ~Ⅱ", "title": "거의 느낄 수 없음",
     "desc": "특별히 좋은 조건에서 극소수만 느끼며, 대부분 지진계에만 기록되는 수준입니다.",
     "video": "z2k9cCdAIWQ", "src": "기상청 실시간 지진 감지 영상", "color": "#90A4AE"},
    {"key": "mid_low", "range": "진도 Ⅲ~Ⅳ", "title": "약한 흔들림",
     "desc": "건물 위층에 있는 사람들이 흔들림을 느끼고, 그릇·창문이 소리를 내는 수준입니다.",
     "video": "oNTGC34kZtU", "src": "2016년 경주 지진 당시 도로 CCTV", "color": "#FBC02D"},
    {"key": "mid", "range": "진도 Ⅴ~Ⅵ", "title": "뚜렷한 흔들림",
     "desc": "거의 모든 사람이 느끼고 놀라서 밖으로 뛰어나가며, 가구가 넘어지기도 합니다.",
     "video": "qo8CEQRwVCA", "src": "2017년 포항 지진 뉴스특보", "color": "#FB8C00"},
    {"key": "high", "range": "진도 Ⅶ~Ⅷ", "title": "구조물 피해 시작",
     "desc": "부실 건축물에 균열과 부분 붕괴가 발생하고, 굴뚝·기둥이 무너지는 수준입니다.",
     "video": "bYDcOPboOYA", "src": "일본 구마모토 규모 7.1 강진 현장", "color": "#E53935"},
    {"key": "extreme", "range": "진도 Ⅸ 이상", "title": "심각한 붕괴",
     "desc": "대부분의 건축물이 기초와 함께 무너지고, 지표면이 심하게 갈라지는 수준입니다.",
     "video": "qgANwS2pm58", "src": "튀르키예 규모 7.8 강진 건물 붕괴", "color": "#8B0035"},
]

# ── CSS ──
st.markdown("""
<style>
html, body, [class*="css"]  { font-size: 18px; }
.hero-box { background: linear-gradient(135deg,#0D1B5E,#B71C1C); padding: 30px 32px;
  border-radius: 16px; color: white; margin-bottom: 18px; }
.hero-title { font-size: 34px; font-weight: 900; margin-bottom: 6px; }
.hero-sub { font-size: 17px; opacity: 0.95; }
.ticker-wrap { width: 100%; overflow: hidden; background: #8B0000; padding: 13px 0;
  border-radius: 8px; margin-bottom: 20px; }
.ticker-move { display: inline-block; white-space: nowrap; padding-left: 100%;
  animation: ticker-scroll 22s linear infinite; color: #fff; font-weight: 800; font-size: 18px; }
@keyframes ticker-scroll { 0% { transform: translate3d(0,0,0); } 100% { transform: translate3d(-100%,0,0); } }
.section-title { font-size: 26px; font-weight: 900; margin: 30px 0 8px 0; color: #0D1B5E;
  border-left: 7px solid #B71C1C; padding-left: 14px; }
.section-sub { font-size: 15px; color: #757575; margin-bottom: 16px; padding-left: 14px; }
.level-card { background: #fff; border-radius: 12px; padding: 18px 10px 16px 10px;
  text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); min-height: 140px;
  overflow: visible; margin-bottom: 8px; }
.level-range { font-size: 24px; font-weight: 900; color: #111; }
.level-title { font-size: 16px; font-weight: 700; color: #444; margin-top: 7px; line-height: 1.4; }
.summary-card { background: #fff; border-radius: 14px; padding: 22px 24px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1); margin-bottom: 14px; min-height: 130px; overflow: visible; }
.summary-card-title { font-size: 16px; color: #616161; font-weight: 700; margin-bottom: 8px; }
.summary-big { font-size: 34px; font-weight: 900; color: #0D1B5E; line-height: 1.3; }
.summary-sub { font-size: 15px; color: #424242; margin-top: 6px; line-height: 1.6; font-weight: 600; }
.legend-row { display: flex; gap: 24px; flex-wrap: wrap; margin: 10px 0 18px 0; font-size: 16px; font-weight: 700; }
.legend-item { display: flex; align-items: center; gap: 7px; }
.legend-box { width: 20px; height: 20px; border-radius: 4px; display: inline-block; }
.behavior-card { background: #EEF2FF; border-radius: 12px; padding: 18px 20px;
  margin-bottom: 10px; min-height: 100px; overflow: visible; }
.behavior-title { font-size: 17px; font-weight: 900; color: #0D1B5E; margin-bottom: 7px; }
.behavior-text { font-size: 15px; color: #222; line-height: 1.65; font-weight: 500; }
.source-note { font-size: 13.5px; color: #9E9E9E; margin-top: 22px; line-height: 1.7; }
</style>
""", unsafe_allow_html=True)

# ── pydeck 안전 변환 헬퍼 ──
def to_records(df):
    """데이터프레임을 pydeck이 안전하게 처리할 수 있는 순수 파이썬 타입 리스트로 변환"""
    if df is None or df.empty:
        return []
    return json.loads(df.to_json(orient="records"))

# ── 데이터 수집 함수 ──
@st.cache_data(ttl=180)
def fetch_recent_eq():
    today = datetime.now()
    params = {
        "ServiceKey": KMA_KEY, "pageNo": 1, "numOfRows": 100, "dataType": "JSON",
        "fromTmFc": (today - timedelta(days=2)).strftime("%Y%m%d"),
        "toTmFc": today.strftime("%Y%m%d"),
    }
    try:
        res = requests.get(KMA_URL, params=params, timeout=10)
        items = res.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        return pd.DataFrame(items)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=21600)
def fetch_history_eq():
    all_items, page, row_size = [], 1, 500
    while True:
        params = {"serviceKey": SAFEMAP_KEY, "pageNo": page, "numOfRows": row_size, "returnType": "JSON"}
        try:
            res = requests.get(SAFEMAP_URL, params=params, timeout=15)
            data = res.json()
        except Exception:
            break
        items = data.get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        if not items:
            break
        all_items.extend(items)
        total = data.get("body", {}).get("totalCount", 0)
        if len(all_items) >= total:
            break
        page += 1
        if page > 20:
            break
    return pd.DataFrame(all_items)

def extract_province(lc):
    if not isinstance(lc, str):
        return "기타(해외 등)"
    for key in PROVINCE_CENTER:
        if lc.startswith(key):
            return key
    return "기타(해외 등)"

def extract_city(lc):
    if not isinstance(lc, str):
        return None
    parts = lc.split(" ")
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return lc

def bin_label(cnt):
    if cnt <= 10:
        return "0~10건"
    elif cnt <= 50:
        return "11~50건"
    elif cnt <= 100:
        return "51~100건"
    else:
        return "100건 초과"

def mag_color(m):
    if pd.isna(m):
        return [158, 158, 158, 160]
    if m < 3:
        return [158, 158, 158, 190]
    elif m < 4:
        return [255, 179, 0, 220]
    elif m < 5:
        return [255, 87, 34, 235]
    return [198, 40, 40, 255]

recent_df = fetch_recent_eq()
history_df = fetch_history_eq()

if not history_df.empty:
    history_df["mag"] = pd.to_numeric(history_df["smints"], errors="coerce")
    history_df["year"] = history_df["occu_de"].astype(str).str[:4]
    history_df["province"] = history_df["lc"].apply(extract_province)
    history_df["city"] = history_df["lc"].apply(extract_city)

if not recent_df.empty:
    recent_df["mag_val"] = pd.to_numeric(recent_df["mt"], errors="coerce")
    recent_df["color"] = recent_df["mag_val"].apply(mag_color)
    recent_df["radius"] = recent_df["mag_val"].fillna(2) * 2500 + 3000
    # pydeck 직렬화 안전을 위해 지도용 컬럼만 남기고 문자열/숫자 타입 정리
    map_recent_df = recent_df[["lat", "lon", "loc", "mt", "inT", "color", "radius"]].copy()
    map_recent_df["lat"] = map_recent_df["lat"].astype(float)
    map_recent_df["lon"] = map_recent_df["lon"].astype(float)
    map_recent_df["radius"] = map_recent_df["radius"].astype(float)
else:
    map_recent_df = pd.DataFrame()

# ── 헤더 ──
st.markdown('<div class="hero-box"><div class="hero-title">🌍 대한민국 지진 현황 알리미</div>'
            '<div class="hero-sub">기상청·행정안전부 공식 데이터를 기반으로 실시간 지진 속보와 최근 발생 이력을 보여드립니다.</div></div>',
            unsafe_allow_html=True)

# ── 상단 실시간 스크롤 배너 ──
if recent_df.empty:
    ticker_items = ["🔴 최근 3일간 국내 지진 속보가 없습니다."]
else:
    ticker_items = []
    for _, row in recent_df.iterrows():
        t = str(row.get("tmEqk", ""))
        tf = f"{t[0:4]}.{t[4:6]}.{t[6:8]} {t[8:10]}:{t[10:12]}" if len(t) >= 12 else t
        ticker_items.append(f"🔴 {tf} · 규모 {row.get('mt','-')} · {row.get('loc','-')}")
content = "&nbsp;&nbsp;|&nbsp;&nbsp;".join(ticker_items * 3)
st.markdown(f'<div class="ticker-wrap"><div class="ticker-move">{content}</div></div>', unsafe_allow_html=True)

# ── 실시간 지진 지도 (최근 3일) ──
st.markdown('<div class="section-title">🗺️ 실시간 지진 발생 지도 (최근 3일)</div>', unsafe_allow_html=True)
if not map_recent_df.empty:
    layer = pdk.Layer("ScatterplotLayer", data=to_records(map_recent_df), get_position='[lon, lat]',
                       get_fill_color='color', get_radius='radius', pickable=True)
    view_state = pdk.ViewState(latitude=36.3, longitude=127.8, zoom=6.6, pitch=0)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, controller=False,
        tooltip={"html": "<b>{loc}</b><br/>규모 {mt}<br/>진도 {inT}"}))
else:
    st.info("최근 3일간 표시할 지진 데이터가 없습니다.")

# ── 규모·진도 설명 + 클릭 영상 ──
st.markdown('<div class="section-title">📊 지진 규모와 진도, 클릭해서 실제 피해 영상을 확인하세요</div>', unsafe_allow_html=True)
if "selected_level" not in st.session_state:
    st.session_state.selected_level = None

cols = st.columns(5)
for i, lv in enumerate(INTENSITY_LEVELS):
    with cols[i]:
        st.markdown(f'<div class="level-card" style="border-top:9px solid {lv["color"]};">'
                    f'<div class="level-range">{lv["range"]}</div>'
                    f'<div class="level-title">{lv["title"]}</div></div>', unsafe_allow_html=True)
        if st.button("▶ 영상보기", key=f"btn_{lv['key']}", use_container_width=True):
            st.session_state.selected_level = lv["key"]

selected = next((l for l in INTENSITY_LEVELS if l["key"] == st.session_state.selected_level), None)
if selected:
    st.markdown(f"### 🎬 {selected['range']} — {selected['title']}")
    st.write(selected["desc"])
    st.video(f"https://www.youtube.com/watch?v={selected['video']}")
    st.caption(f"출처: {selected['src']}")

# ── 예방 행동요령 ──
st.markdown('<div class="section-title">🛡️ 지진 발생 시 국민행동요령</div>', unsafe_allow_html=True)
b1, b2, b3, b4 = st.columns(4)
with b1:
    st.markdown('<div class="behavior-card"><div class="behavior-title">1. 평소 대비</div>'
                '<div class="behavior-text">가구나 물건이 넘어지지 않도록 고정하고, 가족과 대피 장소·통로를 미리 정해둡니다.</div></div>', unsafe_allow_html=True)
with b2:
    st.markdown('<div class="behavior-card"><div class="behavior-title">2. 흔들리는 동안</div>'
                '<div class="behavior-text">탁자 아래로 들어가 몸을 보호하고 탁자 다리를 꼭 잡습니다.</div></div>', unsafe_allow_html=True)
with b3:
    st.markdown('<div class="behavior-card"><div class="behavior-title">3. 흔들림이 멈추면</div>'
                '<div class="behavior-text">전기·가스를 차단하고 신발을 신은 채 계단으로 신속히 대피합니다.</div></div>', unsafe_allow_html=True)
with b4:
    st.markdown('<div class="behavior-card"><div class="behavior-title">4. 장소별 대응</div>'
                '<div class="behavior-text">엘리베이터 안에서는 모든 층 버튼을 눌러 가장 먼저 열리는 층에서 내립니다.</div></div>', unsafe_allow_html=True)

# ── 10년 통계 ──
if not history_df.empty:
    valid_dates = history_df["occu_de"].astype(str)
    valid_dates = valid_dates[valid_dates.str.len() == 8]
    date_min = valid_dates.min()
    date_max = valid_dates.max()
    date_range_str = f"{date_min[:4]}년 {int(date_min[4:6])}월 ~ {date_max[:4]}년 {int(date_max[4:6])}월"
else:
    date_range_str = "-"

st.markdown('<div class="section-title">📈 지진 발생 이력 통계</div>', unsafe_allow_html=True)
st.markdown(f'<div class="section-sub">데이터 기준 기간: <b>{date_range_str}</b> (행정안전부 생활안전지도 등록 데이터, 규모 2.0 이상 전체)</div>', unsafe_allow_html=True)

if not history_df.empty:
    total_count = len(history_df)
    strongest = history_df.loc[history_df["mag"].idxmax()]
    valid_prov = history_df[history_df["province"] != "기타(해외 등)"]

    city_counts = valid_prov["city"].value_counts()
    top_city = city_counts.idxmax() if not city_counts.empty else "-"
    top_city_cnt = city_counts.max() if not city_counts.empty else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="summary-card"><div class="summary-card-title">등록된 전체 지진 이력</div>'
                     f'<div class="summary-big">{total_count:,}건</div>'
                     f'<div class="summary-sub">규모 2.0 이상, 기상청 관측 기준</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="summary-card"><div class="summary-card-title">역대 최대 규모</div>'
                     f'<div class="summary-big">규모 {strongest["mag"]:.1f}</div>'
                     f'<div class="summary-sub">{strongest["lc"]} · {strongest["occu_de"][:4]}년 {int(strongest["occu_de"][4:6])}월 {int(strongest["occu_de"][6:8])}일</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="summary-card"><div class="summary-card-title">발생 최다 지역 (시 단위)</div>'
                     f'<div class="summary-big">{top_city} {top_city_cnt:,}건</div>'
                     f'<div class="summary-sub">전체의 {round(top_city_cnt/total_count*100,1)}%</div></div>', unsafe_allow_html=True)

    yearly_counts = history_df["year"].value_counts().sort_index()
    fig_year = go.Figure(go.Bar(x=yearly_counts.index.tolist(), y=yearly_counts.values.tolist(),
        marker_color="#B71C1C", text=[f"{v:,}건" for v in yearly_counts.values], textposition="outside",
        textfont=dict(size=15, color="#212121")))
    fig_year.update_layout(title=dict(text=f"연도별 지진 발생 건수 ({date_range_str})", font=dict(size=19)),
        height=400, margin=dict(t=60, b=30), yaxis_title="발생 건수", xaxis_title="연도",
        font=dict(size=15))
    st.plotly_chart(fig_year, use_container_width=True, config={"staticPlot": True, "displayModeBar": False})

    mag_labels = ["2.0~2.9", "3.0~3.9", "4.0~4.9", "5.0~5.9", "6.0 이상"]
    history_df["mag_group"] = pd.cut(history_df["mag"], bins=[2,3,4,5,6,10], labels=mag_labels, right=False)
    mag_counts = history_df["mag_group"].value_counts().reindex(mag_labels).fillna(0)
    fig_mag = go.Figure(go.Bar(x=mag_labels, y=mag_counts.values.tolist(),
        marker_color="#D84315", text=[f"{int(v):,}건" for v in mag_counts.values], textposition="outside",
        textfont=dict(size=15, color="#212121")))
    fig_mag.update_layout(title=dict(text="규모별 발생 건수 분포", font=dict(size=19)),
        height=380, margin=dict(t=60, b=30), yaxis_title="발생 건수", xaxis_title="규모 구간",
        font=dict(size=15))
    st.plotly_chart(fig_mag, use_container_width=True, config={"staticPlot": True, "displayModeBar": False})
else:
    st.info("이력 데이터를 불러오지 못했습니다.")

# ── 지역별 빈도 지도 + 막대그래프 ──
st.markdown('<div class="section-title">🎯 지역별 지진 발생 빈도</div>', unsafe_allow_html=True)
st.markdown(f'<div class="section-sub">데이터 기준 기간: <b>{date_range_str}</b></div>', unsafe_allow_html=True)
st.markdown('<div class="legend-row">'
            f'<span class="legend-item"><span class="legend-box" style="background:{BIN_COLORS_HEX["0~10건"]};"></span>0~10건</span>'
            f'<span class="legend-item"><span class="legend-box" style="background:{BIN_COLORS_HEX["11~50건"]};"></span>11~50건</span>'
            f'<span class="legend-item"><span class="legend-box" style="background:{BIN_COLORS_HEX["51~100건"]};"></span>51~100건</span>'
            f'<span class="legend-item"><span class="legend-box" style="background:{BIN_COLORS_HEX["100건 초과"]};"></span>100건 초과</span>'
            '</div>', unsafe_allow_html=True)

if not history_df.empty:
    counts = valid_prov["province"].value_counts().to_dict()
    rows = []
    for prov, (lat, lon) in PROVINCE_CENTER.items():
        cnt = counts.get(prov, 0)
        label = bin_label(cnt)
        radius = 7000 + (cnt ** 0.5) * 3500
        rows.append({"province": prov, "lat": float(lat), "lon": float(lon), "count": int(cnt),
                      "color": BIN_COLORS_RGB[label], "radius": float(radius), "bin_label": label})
    region_df = pd.DataFrame(rows).sort_values("count", ascending=False)

    map_col, bar_col = st.columns([1.1, 1])
    with map_col:
        region_layer = pdk.Layer("ScatterplotLayer", data=to_records(region_df), get_position='[lon, lat]',
                                  get_fill_color='color', get_radius='radius', pickable=True)
        region_view = pdk.ViewState(latitude=36.3, longitude=127.8, zoom=6.4, pitch=0)
        st.pydeck_chart(pdk.Deck(layers=[region_layer], initial_view_state=region_view, controller=False,
            tooltip={"html": "<b>{province}</b><br/>발생 {count}건 ({bin_label})"}))
    with bar_col:
        bar_colors = [BIN_COLORS_HEX[b] for b in region_df["bin_label"]]
        fig_region = go.Figure(go.Bar(
            x=region_df["count"].tolist(), y=region_df["province"].tolist(),
            orientation="h", marker_color=bar_colors,
            text=[f"{v:,}건" for v in region_df["count"]], textposition="outside",
            textfont=dict(size=14, color="#212121")))
        fig_region.update_layout(title=dict(text="시/도별 발생 건수", font=dict(size=19)),
            height=560, margin=dict(t=60, b=30, l=10, r=30),
            yaxis=dict(autorange="reversed", tickfont=dict(size=15)),
            xaxis_title="발생 건수", font=dict(size=14))
        st.plotly_chart(fig_region, use_container_width=True, config={"staticPlot": True, "displayModeBar": False})

st.markdown('<div class="source-note">※ 실시간 배너·지도는 기상청 지진정보 조회서비스(최근 3일), '
            f'이력 통계·지역 지도는 행정안전부 생활안전지도 지진발생이력 데이터({date_range_str}, 규모 2.0 이상)를 기반으로 합니다. '
            '두 데이터의 원 출처는 모두 기상청 관측 자료입니다.</div>', unsafe_allow_html=True)
st.caption(f"마지막 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

"""
app.py — 나의 터빈일지 | 풍력 터빈 손상 탐지 관리자 알람 대시보드

실행:
    pip install streamlit ultralytics
    streamlit run app.py

준비물: best.pt (학습된 모델), severity.py (같은 폴더)
"""
import time
from datetime import datetime

import streamlit as st
import pandas as pd
from PIL import Image
from ultralytics import YOLO

from config import MODEL_PATH
from severity import (
    assess_image,
    GRADE_COLOR, GRADE_BG, GRADE_BORDER,
    GRADE_ACTION, GRADE_GUIDE, CLASS_ICON,
    size_label,
)

# ===== 설정 =====
DISPLAY_CONF_MIN = 0.7          # 화면에 표시할 최소 신뢰도 (판정 로직과는 무관, 표시 전용)

st.set_page_config(page_title="나의 터빈일지", page_icon="🌀", layout="wide")


# ===== 스타일 (산업용 대시보드 톤 — 라이트 테마 고정) =====
st.markdown(
    """
    <style>
    /* ---------- 전역 배경/텍스트 (다크모드 자동전환으로 인한 흰 텍스트 방지) ---------- */
    .stApp { background: #F4F7FB; color: #111827; }
    section.main > div { padding-top: 1.2rem; padding-bottom: 2.5rem; }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4,
    .stApp p, .stApp label, .stApp li { color: #111827; }
    [data-testid="stHeader"] { background: rgba(244, 247, 251, .92); }
    [data-testid="stToolbar"] { color: #334155; }

    .app-header { display: flex; align-items: center; gap: 10px; margin: 0 0 2px; }
    .app-title { color: #0F172A; font-size: 30px; font-weight: 800; margin: 0; line-height: 1.2; }
    .app-subtitle {
        color: #475569; font-size: 14px; margin-top: 2px; margin-bottom: 4px;
    }
    .app-subtitle .en { letter-spacing: .02em; }

    /* ---------- 섹션 제목 ---------- */
    .section-title {
        color: #111827; font-size: 17px; font-weight: 800; margin: 0 0 10px 0;
    }
    .section-sub { color: #64748B; font-size: 12.5px; margin-top: -6px; margin-bottom: 10px; }
    .input-card-title { color: #111827; font-size: 17px; font-weight: 800; margin-bottom: 2px; }
    .input-card-sub { color: #64748B; font-size: 12.5px; margin-bottom: 8px; }

    .fade-in { animation: fadeIn .45s ease-in; }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(6px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* ---------- 공통 카드 스타일 ---------- */
    .kpi-card, .severity-card, .esc-card, .img-card {
        background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px;
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06); padding: 20px;
    }

    /* KPI 카드 */
    .kpi-card {
        padding: 16px 18px;
        transition: transform .15s ease, box-shadow .15s ease;
    }
    .kpi-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 20px rgba(15,23,42,.10);
    }
    .kpi-icon  { font-size: 18px; }
    .kpi-label { font-size: 11px; color: #64748B; text-transform: uppercase;
                 letter-spacing: .06em; font-weight: 700; margin-top: 4px; }
    .kpi-value { font-size: 26px; font-weight: 800; color: #0F172A; margin-top: 2px; }

    /* 심각도 카드 (등급별 좌측 border 컬러는 --grade-color 로 주입) */
    .severity-card {
        border-left: 7px solid var(--grade-color);
    }
    .severity-top { display: flex; align-items: center; gap: 10px; }
    .severity-emoji { font-size: 26px; }
    .severity-grade { font-size: 22px; font-weight: 800; color: var(--grade-color); }
    .severity-score-row { margin-top: 10px; display: flex; align-items: baseline; gap: 8px; }
    .severity-score-label { font-size: 12px; color: #64748B; font-weight: 600; text-transform: uppercase; }
    .severity-score-value { font-size: 30px; font-weight: 800; color: #0F172A; }
    .severity-action {
        margin-top: 10px; font-size: 13px; color: #334155; background: var(--grade-bg);
        border: 1px solid var(--grade-border); border-radius: 8px; padding: 8px 12px;
    }

    /* 리포트(자동 보고서) 카드 — 어두운 카드이므로 흰 글씨 사용 (예외 허용 영역) */
    .report-card {
        background: #0F172A; color: #E2E8F0; border-radius: 16px; padding: 20px;
        margin-top: 18px; font-size: 13px; box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
    }
    .report-card .report-title {
        display: flex; justify-content: space-between; align-items: center;
        font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: #94A3B8;
        margin-bottom: 8px;
    }
    .report-card .report-badge {
        background: #1E293B; color: #38BDF8; padding: 2px 8px; border-radius: 999px; font-size: 10px;
    }
    .report-card .report-row { display: flex; justify-content: space-between; padding: 3px 0; }
    .report-card .report-row span:first-child { color: #94A3B8; }
    .report-card .report-row span:last-child { font-weight: 700; color: #F1F5F9; }

    /* 에스컬레이션 카드 */
    .esc-header { font-size: 14px; font-weight: 800; color: #0F172A; margin-bottom: 10px; }
    .esc-row { margin-bottom: 8px; }
    .esc-row-label { font-size: 11px; color: #64748B; font-weight: 700; text-transform: uppercase;
                      margin-right: 6px; }
    .chip {
        display: inline-flex; align-items: center; gap: 5px; background: #F1F5F9;
        border: 1px solid #E2E8F0; border-radius: 999px; padding: 3px 11px; margin: 3px 5px 0 0;
        font-size: 12.5px; font-weight: 600; color: #334155;
    }
    .esc-note {
        margin-top: 6px; font-size: 12.5px; font-weight: 600; border-radius: 8px;
        padding: 8px 12px; background: var(--grade-bg); color: var(--grade-color);
        border: 1px solid var(--grade-border);
    }

    /* 등급 범례 */
    .legend-row { display: flex; align-items: center; gap: 8px; font-size: 13px; padding: 3px 0; color: #111827; }
    .legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }

    /* ---------- 점검 입력 카드 (max-width + 높이 정렬) ---------- */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.input-card-anchor),
    div[data-testid="stLayoutWrapper"]:has(.input-card-anchor) {
        max-width: 960px; margin: 0 auto 8px;
        background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px;
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.input-card-anchor) > div,
    div[data-testid="stLayoutWrapper"]:has(.input-card-anchor) > div {
        background: #FFFFFF; border-radius: 16px;
    }
    /* 입력 컬럼: 68/28 비율, 동일한 기준선과 24px 간격 */
    [data-testid="stHorizontalBlock"]:has([data-testid="stFileUploader"]):has([data-testid="stTextInput"]) {
        display: flex; align-items: flex-end; gap: 24px;
    }
    [data-testid="stHorizontalBlock"]:has([data-testid="stFileUploader"]):has([data-testid="stTextInput"]) > div:first-child {
        flex: 0 1 68%; width: 68%;
    }
    [data-testid="stHorizontalBlock"]:has([data-testid="stFileUploader"]):has([data-testid="stTextInput"]) > div:last-child {
        flex: 0 1 28%; width: 28%;
    }
    [data-testid="stFileUploader"], [data-testid="stTextInput"] {
        width: 100%;
    }
    [data-testid="stFileUploader"] [data-testid="stWidgetLabel"],
    [data-testid="stTextInput"] [data-testid="stWidgetLabel"] {
        min-height: 24px; margin-bottom: 6px; display: flex; align-items: center;
    }
    [data-testid="stFileUploaderDropzone"] {
        box-sizing: border-box; min-height: 56px; height: 56px; padding: 0 16px;
        display: flex; align-items: center; background: #F8FAFC;
        border-color: #CBD5E1; border-radius: 12px;
    }
    [data-testid="stFileUploaderDropzone"] > div {
        width: 100%; display: flex; align-items: center; min-height: 0; padding: 0;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] svg { display: none; }
    [data-testid="stFileUploaderDropzoneInstructions"] {
        display: flex; flex-direction: column; justify-content: center; min-height: 0;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] span,
    [data-testid="stFileUploaderDropzoneInstructions"] small { font-size: 12px; }
    [data-testid="stFileUploader"] section { padding: 0; margin: 0; }
    [data-testid="stTextInput"] input {
        box-sizing: border-box; height: 56px; min-height: 56px; padding: 0 16px;
        line-height: 56px; font-size: 15px; background: #F8FAFC; color: #0F172A;
        border-color: #CBD5E1; border-radius: 12px !important;
    }
    [data-testid="stTextInput"] > div,
    [data-testid="stTextInput"] [data-baseweb="input"] {
        min-height: 56px; height: 56px; display: flex; align-items: center;
        border-radius: 12px;
    }
    [data-testid="stFileUploaderDropzone"] { margin-top: 0; }
    [data-testid="stWidgetLabel"] p { color: #334155; font-weight: 600; font-size: 13px; }
    div[data-testid="stFileUploaderFile"] {
        box-sizing: border-box; min-height: 56px; height: 56px; margin: 0; padding: 0 14px;
        display: flex; align-items: center; color: #111827; background: #F8FAFC;
        border: 1px solid #CBD5E1; border-radius: 12px;
    }
    div[data-testid="stFileUploaderFile"] > div {
        min-height: 0; display: flex; align-items: center;
    }
    div[data-testid="stFileUploaderFile"] button {
        align-self: center; margin: 0;
    }
    [data-testid="stFileUploader"]:has([data-testid="stFileUploaderFile"])
    [data-testid="stFileUploaderDropzone"] { display: none; }

    /* 심각도와 등급 안내를 시각적으로 분리 */
    .severity-card { margin-bottom: 14px; }
    [data-testid="stElementContainer"]:has(.severity-card) +
    [data-testid="stElementContainer"] [data-testid="stExpander"] { margin-top: 12px; }

    /* ---------- 탐지 이미지 카드 ---------- */
    [data-testid="stImage"] {
        background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px;
        padding: 10px; box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
    }
    [data-testid="stImage"] img {
        max-height: 560px; width: 100%; object-fit: contain; border-radius: 12px;
    }
    [data-testid="stCaptionContainer"], .stCaption { color: #64748B !important; }

    /* ---------- 데이터프레임(표) 라이트 스타일 ---------- */
    [data-testid="stDataFrame"] {
        border: 1px solid #E5E7EB; border-radius: 12px; overflow: hidden;
        background: #FFFFFF; color: #111827;
    }
    [data-testid="stDataFrame"] canvas { color-scheme: light; }
    [data-testid="stCheckbox"] p { color: #334155; }
    [data-testid="stExpander"] { background: #FFFFFF; border-color: #E5E7EB; }
    [data-testid="stExpander"] summary p { color: #334155; }
    hr { border-color: #E2E8F0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_model():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {MODEL_PATH}")
    return YOLO(str(MODEL_PATH))


def channel_badges(channels):
    """알림 채널 문자열 → (아이콘, 라벨) 배지 목록 (표시 전용)"""
    badges = []
    for ch in channels:
        low = ch.lower()
        if "로그" in ch:
            badges.append(("📝", "로그 기록"))
        if "대시보드" in ch:
            badges.append(("📊", "Dashboard"))
        if "이메일" in ch:
            badges.append(("📧", "Email"))
        if "팀" in ch and "메시지" in ch:
            badges.append(("💬", "팀 메시지"))
        if "slack" in low:
            badges.append(("🚨", "Slack") if "즉시" in ch else ("💬", "Slack"))
        if "sms" in low:
            badges.append(("📱", "SMS"))
    return badges


def target_badges(targets):
    """알림 대상 문자열 → (아이콘, 라벨) 배지 목록 (표시 전용)"""
    badges = []
    for t in targets:
        if "현장" in t:
            badges.append(("👷", "현장 담당자"))
        elif t == "팀":
            badges.append(("👥", "팀"))
        elif "관리자" in t or "책임자" in t:
            badges.append(("👨‍💼", "관리자/책임자"))
        else:
            badges.append(("👤", t))
    return badges


def render_chips(badges):
    return "".join(f"<span class='chip'>{icon} {label}</span>" for icon, label in badges)


def kpi_card(icon, label, value):
    st.markdown(
        f"""<div class="kpi-card fade-in">
                <div class="kpi-icon">{icon}</div>
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
            </div>""",
        unsafe_allow_html=True,
    )


# 세션에 점검 이력 저장 (터빈일지)
if "history" not in st.session_state:
    st.session_state.history = []


# ===== 헤더 =====
st.markdown(
    "<div class='app-header'><span class='app-title'>🌀 나의 터빈일지</span></div>"
    "<div class='app-subtitle'>AI 기반 풍력터빈 손상 탐지 · "
    "<span class='en'>Predictive Maintenance Dashboard</span></div>",
    unsafe_allow_html=True,
)
st.divider()

model = load_model()

# ===== 입력 =====
with st.container(border=True):
    st.markdown(
        "<div class='input-card-anchor'></div>"
        "<div class='input-card-title'>점검 입력</div>"
        "<div class='input-card-sub'>점검 이미지와 관리 대상 터빈을 입력하세요.</div>",
        unsafe_allow_html=True,
    )
    col_in, col_id = st.columns([7, 3], gap="medium")
    with col_in:
        uploaded = st.file_uploader("터빈 이미지 업로드", type=["jpg", "jpeg", "png"])
    with col_id:
        turbine_id = st.text_input("터빈 ID", value="터빈-03")

if uploaded:
    # ===== 순차 진행 상태 표시 =====
    with st.status("분석 진행 중...", expanded=True) as status:
        st.write("🖼️ 이미지 로드 중...")
        img = Image.open(uploaded).convert("RGB")
        tmp_path = "_tmp_upload.jpg"
        img.save(tmp_path)
        time.sleep(0.3)

        st.write("🔎 YOLO 탐지 진행 중...")
        result = assess_image(model, tmp_path, turbine_id=turbine_id)
        yolo_res = result["yolo_result"]
        time.sleep(0.3)

        st.write("📐 심각도 계산 중...")
        time.sleep(0.3)

        grade = result["grade"]
        color = GRADE_COLOR[grade]
        st.write(f"{result['emoji']} 등급 판정 완료 — {grade}")
        time.sleep(0.3)

        st.write("📢 에스컬레이션 정책 확인 중...")
        time.sleep(0.3)

        status.update(label="분석 완료", state="complete", expanded=False)

    st.write("")

    # ===== 결과: 좌(이미지) 우(판정) =====
    col_img, col_res = st.columns([3, 2], gap="large")

    with col_img:
        st.markdown("<div class='section-title'>탐지 결과</div>", unsafe_allow_html=True)
        # 화면에는 신뢰도 0.7 이상 탐지만 표시 (심각도 계산은 원본 결과 기준 유지)
        display_res = yolo_res[yolo_res.boxes.conf >= DISPLAY_CONF_MIN]
        plotted = display_res.plot()[:, :, ::-1]
        st.image(plotted, width="stretch")
        st.caption(f"신뢰도 {int(DISPLAY_CONF_MIN*100)}% 이상 탐지 결과만 화면에 표시됩니다. "
                   "낮은 확신도는 재확인 대상으로 분류됩니다.")

    with col_res:
        grade_bg, grade_border = GRADE_BG[grade], GRADE_BORDER[grade]
        css_vars = f"--grade-color:{color};--grade-bg:{grade_bg};--grade-border:{grade_border};"

        # --- 심각도 카드 ---
        st.markdown(
            f"""<div class="severity-card fade-in" style="{css_vars}">
                    <div class="severity-top">
                        <span class="severity-emoji">{result['emoji']}</span>
                        <span class="severity-grade">{grade}</span>
                    </div>
                    <div class="severity-score-row">
                        <span class="severity-score-label">위험도</span>
                        <span class="severity-score-value">{result['score']}</span>
                    </div>
                    <div class="severity-action">권장 조치 · {GRADE_ACTION[grade]}</div>
                </div>""",
            unsafe_allow_html=True,
        )

        with st.expander("ℹ️ 등급 기준 안내"):
            for g in ["정상", "관찰", "주의", "위험"]:
                st.markdown(
                    f"<div class='legend-row'>"
                    f"<span class='legend-dot' style='background:{GRADE_COLOR[g]}'></span>"
                    f"<b>{g}</b> — {GRADE_GUIDE[g]}</div>",
                    unsafe_allow_html=True,
                )

        # --- 자동 보고서 카드 ---
        st.markdown(
            f"""<div class="report-card fade-in">
                    <div class="report-title">점검 결과 <span class="report-badge">AUTO REPORT</span></div>
                    <div class="report-row"><span>터빈</span><span>{turbine_id}</span></div>
                    <div class="report-row"><span>Damage</span><span>{result['n_damage']}건</span></div>
                    <div class="report-row"><span>Dirt</span><span>{result['n_dirt']}건</span></div>
                    <div class="report-row"><span>위험도</span><span>{result['score']}</span></div>
                    <div class="report-row"><span>권장조치</span><span>{GRADE_GUIDE[grade]}</span></div>
                    <div class="report-row"><span>시간</span><span>{datetime.now().strftime('%Y-%m-%d %H:%M')}</span></div>
                </div>""",
            unsafe_allow_html=True,
        )

        st.write("")

        # --- KPI 카드 ---
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card(CLASS_ICON["Damage"], "Damage", f"{result['n_damage']}건")
        with c2:
            kpi_card(CLASS_ICON["Dirt"], "Dirt", f"{result['n_dirt']}건")
        with c3:
            kpi_card("👁", "재확인", f"{result['recheck']}건")

        st.write("")

        # --- 에스컬레이션 카드 ---
        ch_badges = render_chips(channel_badges(result["channels"]))
        tg_badges = render_chips(target_badges(result["targets"])) or (
            "<span class='chip'>없음</span>"
        )
        if grade == "정상":
            note = "🟢 이상 없음 — 로그에만 기록됩니다."
        elif grade == "위험":
            note = "🚨 즉시 발송 예정"
        elif grade == "주의":
            note = "📧 발송 예정"
        else:
            note = "📊 대시보드 표시 예정"

        st.markdown(
            f"""<div class="esc-card fade-in" style="{css_vars}">
                    <div class="esc-header">📢 알림 정책</div>
                    <div class="esc-row"><div class="esc-row-label">채널</div>{ch_badges}</div>
                    <div class="esc-row"><div class="esc-row-label">대상</div>{tg_badges}</div>
                    <div class="esc-note">{note}</div>
                </div>""",
            unsafe_allow_html=True,
        )

        if result["recheck"] > 0:
            st.caption(f"⚠️ 확신도 낮은 탐지 {result['recheck']}건은 자동 판정에서 제외 — 담당자 재확인 권장")

    st.write("")

    # ===== 탐지 상세 표 =====
    if result["counted"] or result["recheck_list"]:
        st.markdown("<div class='section-title'>탐지 상세</div>", unsafe_allow_html=True)
        rows = []
        for d in sorted(result["counted"], key=lambda d: -d["conf"]):
            rows.append({
                "클래스": f"{CLASS_ICON.get(d['label'], '')} {d['label']}",
                "크기": size_label(d["area_ratio"]),
                "신뢰도": f"{d['conf']*100:.0f}%",
                "처리": "✅ 반영",
            })
        for d in sorted(result["recheck_list"], key=lambda d: -d["conf"]):
            rows.append({
                "클래스": f"{CLASS_ICON.get(d['label'], '')} {d['label']}",
                "크기": size_label(d["area_ratio"]),
                "신뢰도": f"{d['conf']*100:.0f}%",
                "처리": "⚠ 재확인",
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    # ===== 점검 이력 기록 =====
    st.session_state.history.insert(0, {
        "시각": datetime.now().strftime("%H:%M:%S"),
        "터빈": turbine_id,
        "등급": f"{result['emoji']} {grade}",
        "위험도": result["score"],
        "Damage": result["n_damage"],
        "Dirt": result["n_dirt"],
    })

# ===== 점검 이력 (터빈일지) =====
st.divider()
st.markdown("<div class='section-title'>📒 점검 이력 (터빈일지)</div>", unsafe_allow_html=True)
if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)
    if st.checkbox("위험도 높은 순으로 정렬"):
        df = df.sort_values("위험도", ascending=False)

    def _tint_row(row):
        for g, bg in GRADE_BG.items():
            if g in row["등급"]:
                return [f"background-color:{bg}"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df.style.apply(_tint_row, axis=1),
        width="stretch", hide_index=True,
        column_config={"위험도": st.column_config.NumberColumn("위험도", format="%.1f")},
    )
else:
    st.caption("아직 점검 이력이 없습니다. 이미지를 업로드하세요.")

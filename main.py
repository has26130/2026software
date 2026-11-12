import time
from datetime import datetime
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 커스텀 CSS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="열공 스터디 플래너 | 공부타이머 · 오늘 할일 · 공부회고",
    page_icon="⏱️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2.5rem;
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(168, 85, 247, 0.05));
        border: 1px solid rgba(99, 102, 241, 0.2);
        padding: 14px 18px;
        border-radius: 14px;
    }
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        height: 3.1rem;
        transition: all 0.15s ease-in-out;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 2. 세션 상태(Session State) 초기화 (페이지 이동 시에도 타이머/기록 100% 유지)
# -----------------------------------------------------------------------------
DEFAULT_SUBJECTS = ["국어", "수학", "영어", "한국사", "탐구(사회/과학)", "제2외국어/한문", "기타/자습"]

if "subjects" not in st.session_state:
    st.session_state.subjects = DEFAULT_SUBJECTS.copy()

if "current_subject" not in st.session_state:
    st.session_state.current_subject = st.session_state.subjects[0]

if "is_running" not in st.session_state:
    st.session_state.is_running = False

if "start_time" not in st.session_state:
    st.session_state.start_time = None

if "accumulated_sec" not in st.session_state:
    st.session_state.accumulated_sec = 0.0

if "study_logs" not in st.session_state:
    st.session_state.study_logs = []

if "daily_goal_min" not in st.session_state:
    st.session_state.daily_goal_min = 180  # 기본 일일 목표: 3시간(180분)

if "session_memo" not in st.session_state:
    st.session_state.session_memo = ""


# -----------------------------------------------------------------------------
# 3. 시간 계산 및 포맷팅 유틸리티 함수
# -----------------------------------------------------------------------------
def get_elapsed_seconds() -> float:
    """현재 타이머의 정확한 누적 경과 시간(초)을 반환합니다."""
    if st.session_state.is_running and st.session_state.start_time is not None:
        return st.session_state.accumulated_sec + (time.time() - st.session_state.start_time)
    return st.session_state.accumulated_sec


def format_hms(seconds: float) -> str:
    """초(seconds)를 HH:MM:SS 문자열로 변환합니다."""
    total_sec = max(0, int(round(seconds)))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_korean_duration(seconds: float) -> str:
    """초(seconds)를 읽기 쉬운 한국어 시간 문자열로 변환합니다."""
    total_sec = max(0, int(round(seconds)))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours}시간 {minutes}분 {secs}초"
    if minutes > 0:
        return f"{minutes}분 {secs}초"
    return f"{secs}초"


# -----------------------------------------------------------------------------
# 4. 타이머 제어 콜백 함수 (시작 / 일시정지 / 초기화 / 과목별 기록)
# -----------------------------------------------------------------------------
def start_timer() -> None:
    if not st.session_state.is_running:
        st.session_state.start_time = time.time()
        st.session_state.is_running = True
        st.toast(f"▶️ [{st.session_state.current_subject}] 학습 타이머를 시작합니다!", icon="🔥")


def pause_timer() -> None:
    if st.session_state.is_running and st.session_state.start_time is not None:
        st.session_state.accumulated_sec += time.time() - st.session_state.start_time
        st.session_state.start_time = None
        st.session_state.is_running = False
        st.toast(
            f"⏸️ 타이머가 일시정지되었습니다. (현재 {format_hms(st.session_state.accumulated_sec)})",
            icon="⏸️",
        )


def reset_timer() -> None:
    st.session_state.is_running = False
    st.session_state.start_time = None
    st.session_state.accumulated_sec = 0.0
    st.toast("🔄 타이머가 00:00:00으로 초기화되었습니다.", icon="🔄")


def save_study_record(subject: str, memo: str) -> None:
    elapsed = get_elapsed_seconds()
    total_sec = int(round(elapsed))

    if total_sec < 1:
        st.toast("⚠️ 최소 1초 이상 학습한 후 기록을 저장할 수 있습니다.", icon="⚠️")
        return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_memo = memo.strip() if memo and memo.strip() else "일반 자습"

    st.session_state.study_logs.append(
        {
            "기록시각": now_str,
            "과목": subject,
            "학습시간(초)": total_sec,
            "학습시간(분)": round(total_sec / 60, 2),
            "포맷시간": format_hms(total_sec),
            "학습메모": clean_memo,
        }
    )

    # 기록 후 타이머 자동 초기화 (다음 과목 바로 측정 가능)
    st.session_state.is_running = False
    st.session_state.start_time = None
    st.session_state.accumulated_sec = 0.0
    st.session_state.session_memo = ""
    st.toast(
        f"✅ [{subject}] {format_korean_duration(total_sec)} 학습 기록이 저장되었습니다!",
        icon="🎉",
    )


# -----------------------------------------------------------------------------
# 5. 실시간 무깜빡임(Zero-Flicker) JS 하이브리드 타이머 디스플레이 컴포넌트
# -----------------------------------------------------------------------------
def render_realtime_timer(
    base_elapsed_sec: float,
    is_running: bool,
    subject: str,
    memo: str,
    goal_min: int,
    today_saved_sec: int,
) -> None:
    """
    서버 리렌더링 없이 브라우저에서 1초 단위로 부드럽게 흐르는 디지털 타이머를 렌더링합니다.
    시작/일시정지/초기화/기록 버튼 클릭 시에는 Python의 time.time() 델타 값과 100% 동기화됩니다.
    """
    status_text = "LIVE 학습 측정 중" if is_running else ("일시정지됨" if base_elapsed_sec > 0 else "측정 대기 중")
    status_color = "#10B981" if is_running else ("#F59E0B" if base_elapsed_sec > 0 else "#64748B")
    pulse_css = "animation: pulse 1.5s infinite;" if is_running else ""
    safe_memo = memo.strip() if memo and memo.strip() else "목표를 향해 집중하는 시간!"

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        }}
        body {{
            background: transparent;
            padding: 4px;
        }}
        .timer-card {{
            background: linear-gradient(135deg, #1E1B4B 0%, #312E81 55%, #1E293B 100%);
            color: #F8FAFC;
            border-radius: 20px;
            padding: 26px 28px;
            box-shadow: 0 12px 28px rgba(30, 27, 75, 0.25);
            border: 1px solid rgba(255, 255, 255, 0.12);
            text-align: center;
        }}
        .top-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .subject-badge {{
            background: rgba(99, 102, 241, 0.35);
            border: 1px solid rgba(129, 140, 248, 0.6);
            color: #E0E7FF;
            padding: 6px 15px;
            border-radius: 999px;
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 0.3px;
        }}
        .status-pill {{
            display: inline-flex;
            align-items: center;
            gap: 7px;
            background: rgba(15, 23, 42, 0.55);
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
            color: #E2E8F0;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .dot {{
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background-color: {status_color};
            {pulse_css}
        }}
        @keyframes pulse {{
            0% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
            70% {{ box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
        }}
        .clock-display {{
            font-size: 4.4rem;
            font-weight: 800;
            font-variant-numeric: tabular-nums;
            letter-spacing: 3px;
            margin: 12px 0 8px 0;
            color: #FFFFFF;
            text-shadow: 0 4px 18px rgba(99, 102, 241, 0.45);
        }}
        .memo-text {{
            font-size: 0.95rem;
            color: #CBD5E1;
            margin-bottom: 18px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .progress-wrap {{
            background: rgba(15, 23, 42, 0.6);
            border-radius: 999px;
            height: 10px;
            width: 100%;
            overflow: hidden;
            margin-bottom: 8px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .progress-bar {{
            background: linear-gradient(90deg, #38BDF8, #818CF8, #C084FC);
            height: 100%;
            width: 0%;
            transition: width 0.3s ease;
        }}
        .progress-info {{
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
            color: #94A3B8;
            font-weight: 500;
        }}
    </style>
    </head>
    <body>
        <div class="timer-card">
            <div class="top-row">
                <span class="subject-badge">📚 현재 과목: {subject}</span>
                <span class="status-pill"><span class="dot"></span>{status_text}</span>
            </div>
            <div id="clock" class="clock-display">00:00:00</div>
            <div class="memo-text">📝 {safe_memo}</div>
            <div class="progress-wrap">
                <div id="goal-bar" class="progress-bar"></div>
            </div>
            <div class="progress-info">
                <span id="total-live-label">오늘 누적(현재 세션 포함): 00:00:00</span>
                <span id="goal-pct-label">일일 목표({goal_min}분) 달성률: 0.0%</span>
            </div>
        </div>

        <script>
            const baseElapsed = {base_elapsed_sec:.3f};
            const isRunning = {"true" if is_running else "false"};
            const todaySavedSec = {today_saved_sec};
            const goalSec = Math.max(60, {goal_min * 60});
            const loadTimestamp = Date.now();

            function pad(n) {{
                return String(n).padStart(2, '0');
            }}

            function formatHMS(sec) {{
                const total = Math.max(0, Math.floor(sec));
                const h = Math.floor(total / 3600);
                const m = Math.floor((total % 3600) / 60);
                const s = total % 60;
                return `${{pad(h)}}:${{pad(m)}}:${{pad(s)}}`;
            }}

            function updateClock() {{
                let currentSec = baseElapsed;
                if (isRunning) {{
                    currentSec += (Date.now() - loadTimestamp) / 1000.0;
                }}
                document.getElementById('clock').textContent = formatHMS(currentSec);

                const totalToday = todaySavedSec + currentSec;
                const pct = Math.min(100, (totalToday / goalSec) * 100);
                document.getElementById('goal-bar').style.width = pct.toFixed(1) + '%';
                document.getElementById('total-live-label').textContent =
                    `오늘 총 학습(현재 포함): ${{formatHMS(totalToday)}}`;
                document.getElementById('goal-pct-label').textContent =
                    `일일 목표({goal_min}분) 달성률: ${{pct.toFixed(1)}}%`;
            }}

            updateClock();
            if (isRunning) {{
                setInterval(updateClock, 200);
            }}
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=255)


# -----------------------------------------------------------------------------
# 6. 사이드바: 3대 메뉴 네비게이션 (공부타이머 / 오늘 할일 / 공부회고)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("📌 메뉴 선택")
    selected_menu = st.radio(
        "이동할 메뉴를 선택하세요",
        options=["공부타이머", "오늘 할일", "공부회고"],
        index=0,
        label_visibility="collapsed",
    )

    if selected_menu == "공부타이머":
        st.divider()
        st.header("⚙️ 학습 환경 설정")

        st.subheader("🎯 일일 목표 학습 시간")
        st.session_state.daily_goal_min = st.slider(
            "하루 목표 시간(분)",
            min_value=30,
            max_value=720,
            value=st.session_state.daily_goal_min,
            step=30,
            help="하루 목표 학습 시간을 설정하면 실시간 달성률이 표시됩니다.",
        )
        st.caption(
            f"설정된 일일 목표: **{st.session_state.daily_goal_min // 60}시간 {st.session_state.daily_goal_min % 60}분**"
        )

        st.divider()

        st.subheader("➕ 나만의 과목 추가")
        with st.form("add_subject_form", clear_on_submit=True):
            new_subject = st.text_input("새 과목 이름", placeholder="예: 물리학I, 코딩, 한국지리")
            submitted = st.form_submit_button("과목 추가하기", use_container_width=True)
            if submitted:
                cleaned = new_subject.strip()
                if not cleaned:
                    st.warning("과목 이름을 입력해주세요.")
                elif cleaned in st.session_state.subjects:
                    st.warning("이미 등록된 과목입니다.")
                else:
                    st.session_state.subjects.append(cleaned)
                    st.session_state.current_subject = cleaned
                    st.success(f"'{cleaned}' 과목이 추가되었습니다!")
                    st.rerun()

        st.divider()
        st.subheader("🗑️ 기록 관리")
        if st.button("전체 학습 기록 초기화", use_container_width=True):
            st.session_state.study_logs = []
            st.toast("모든 학습 기록이 초기화되었습니다.", icon="🗑️")
            st.rerun()

    st.divider()
    st.subheader("📦 소스 파일 다운로드")
    try:
        current_code = Path(__file__).read_text(encoding="utf-8")
        st.download_button(
            label="📄 main.py 다운로드",
            data=current_code.encode("utf-8"),
            file_name="main.py",
            mime="text/x-python",
            use_container_width=True,
        )
    except Exception:
        pass

    req_content = "streamlit\npandas\nplotly\n"
    st.download_button(
        label="📄 requirements.txt 다운로드",
        data=req_content.encode("utf-8"),
        file_name="requirements.txt",
        mime="text/plain",
        use_container_width=True,
    )


# -----------------------------------------------------------------------------
# 7. 메뉴별 페이지 렌더링
# -----------------------------------------------------------------------------
if selected_menu == "공부타이머":
    # [메뉴 1] 공부타이머 (기존 학습 타이머 전체 기능)
    st.title("⏱️ 공부타이머")
    st.caption("과목별로 집중 시간을 측정하고, 오늘 공부한 내용을 체계적으로 기록·분석하세요.")

    total_saved_sec = sum(item["학습시간(초)"] for item in st.session_state.study_logs)
    session_count = len(st.session_state.study_logs)

    if st.session_state.study_logs:
        df_temp = pd.DataFrame(st.session_state.study_logs)
        subject_totals = df_temp.groupby("과목")["학습시간(초)"].sum()
        top_subject = subject_totals.idxmax()
    else:
        top_subject = "-"

    goal_achievement = min(
        100.0, (total_saved_sec / max(1, st.session_state.daily_goal_min * 60)) * 100
    )

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("총 누적 학습 시간 (저장됨)", format_hms(total_saved_sec))
    kpi2.metric("완료한 학습 세션", f"{session_count}회")
    kpi3.metric("최다 집중 과목", top_subject)
    kpi4.metric("일일 목표 달성률", f"{goal_achievement:.1f}%")

    st.markdown("---")

    left_col, right_col = st.columns([1.15, 1.0], gap="large")

    with left_col:
        st.subheader("🎯 과목 선택 및 타이머 제어")

        sub_col1, sub_col2 = st.columns([1, 1.3])
        with sub_col1:
            selected_subject = st.selectbox(
                "📚 공부할 과목 선택",
                options=st.session_state.subjects,
                index=st.session_state.subjects.index(st.session_state.current_subject)
                if st.session_state.current_subject in st.session_state.subjects
                else 0,
                disabled=st.session_state.is_running,
                help="타이머가 작동 중일 때는 과목 변경이 잠깁니다. 일시정지 또는 기록 저장 후 변경하세요.",
            )
            st.session_state.current_subject = selected_subject

        with sub_col2:
            memo_input = st.text_input(
                "📝 이번 세션 학습 목표 / 단원 메모",
                value=st.session_state.session_memo,
                placeholder="예: 수I 지수로그 기출 30제 풀이",
            )
            st.session_state.session_memo = memo_input

        # 실시간 하이브리드 타이머 렌더링
        current_elapsed = get_elapsed_seconds()
        render_realtime_timer(
            base_elapsed_sec=current_elapsed,
            is_running=st.session_state.is_running,
            subject=st.session_state.current_subject,
            memo=st.session_state.session_memo,
            goal_min=st.session_state.daily_goal_min,
            today_saved_sec=total_saved_sec,
        )

        # 4대 핵심 버튼: 시작 / 일시정지 / 초기화 / 과목별 기록 저장
        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

        with btn_col1:
            if st.button(
                "▶️ 시작",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.is_running,
            ):
                start_timer()
                st.rerun()

        with btn_col2:
            if st.button(
                "⏸️ 일시정지",
                use_container_width=True,
                disabled=not st.session_state.is_running,
            ):
                pause_timer()
                st.rerun()

        with btn_col3:
            if st.button(
                "🔄 초기화",
                use_container_width=True,
                disabled=(not st.session_state.is_running and current_elapsed == 0),
            ):
                reset_timer()
                st.rerun()

        with btn_col4:
            if st.button(
                "💾 기록 저장",
                use_container_width=True,
                help="현재 측정된 시간을 선택된 과목으로 기록하고 타이머를 초기화합니다.",
            ):
                save_study_record(st.session_state.current_subject, st.session_state.session_memo)
                st.rerun()

        st.info(
            "💡 **사용 팁**: **시작**을 누르면 타이머가 작동하며, 공부를 마친 뒤 **기록 저장**을 누르면 "
            "우측의 과목별 통계와 하단 기록표에 즉시 누적됩니다."
        )

    with right_col:
        st.subheader("📊 과목별 누적 학습 시간 분석")

        if not st.session_state.study_logs:
            st.markdown(
                """
                <div style="background: rgba(148, 163, 184, 0.08); border: 1px dashed rgba(148, 163, 184, 0.4);
                            border-radius: 16px; padding: 48px 24px; text-align: center; color: #64748B; margin-top: 12px;">
                    <h4 style="margin-bottom: 8px;">아직 저장된 학습 기록이 없습니다 📭</h4>
                    <p style="font-size: 0.92rem;">왼쪽 타이머에서 과목을 선택하고 <b>▶️ 시작</b> 후 <b>💾 기록 저장</b>을 눌러보세요!</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            df_logs = pd.DataFrame(st.session_state.study_logs)

            # 과목별 집계 테이블 생성
            summary_df = (
                df_logs.groupby("과목", as_index=False)
                .agg(
                    세션수=("학습시간(초)", "count"),
                    총학습초=("학습시간(초)", "sum"),
                )
                .sort_values(by="총학습초", ascending=False)
            )
            summary_df["누적 시간"] = summary_df["총학습초"].apply(format_hms)
            summary_df["비중(%)"] = (
                (summary_df["총학습초"] / summary_df["총학습초"].sum()) * 100
            ).round(1)
            summary_df["학습시간(분)"] = (summary_df["총학습초"] / 60.0).round(1)

            tab_chart, tab_table = st.tabs(["🍩 과목별 비율 차트", "📋 과목별 요약표"])

            with tab_chart:
                fig = px.pie(
                    summary_df,
                    names="과목",
                    values="총학습초",
                    hole=0.48,
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                )
                fig.update_traces(
                    textposition="inside",
                    textinfo="percent+label",
                    hovertemplate="<b>%{label}</b><br>비중: %{percent}<extra></extra>",
                )
                fig.update_layout(
                    margin=dict(t=15, b=15, l=15, r=15),
                    height=280,
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
                )
                st.plotly_chart(fig, use_container_width=True)

            with tab_table:
                display_summary = summary_df[["과목", "세션수", "누적 시간", "학습시간(분)", "비중(%)"]].reset_index(
                    drop=True
                )
                st.dataframe(display_summary, use_container_width=True, hide_index=True)

    # 하단: 세션별 상세 학습 기록 히스토리 및 CSV 다운로드
    st.markdown("---")
    st.subheader("🗂️ 과목별 상세 학습 기록 히스토리")

    if st.session_state.study_logs:
        df_history = pd.DataFrame(st.session_state.study_logs)

        filter_col1, filter_col2 = st.columns([1, 2])
        with filter_col1:
            recorded_subjects = ["전체 보기"] + sorted(df_history["과목"].unique().tolist())
            selected_filter = st.selectbox("과목별 필터링", options=recorded_subjects)

        if selected_filter != "전체 보기":
            filtered_df = df_history[df_history["과목"] == selected_filter].copy()
        else:
            filtered_df = df_history.copy()

        # 최신 기록이 위로 오도록 정렬
        filtered_df = filtered_df.iloc[::-1].reset_index(drop=True)

        st.dataframe(
            filtered_df[["기록시각", "과목", "포맷시간", "학습시간(분)", "학습메모"]].rename(
                columns={"포맷시간": "학습시간(HH:MM:SS)"}
            ),
            use_container_width=True,
            hide_index=True,
        )

        # 엑셀에서도 한글이 깨지지 않는 UTF-8-SIG CSV 다운로드 버튼
        csv_bytes = df_history.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 전체 학습 기록 CSV 다운로드 (엑셀 호환)",
            data=csv_bytes,
            file_name=f"study_timer_records_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )
    else:
        st.caption("저장된 세션 기록이 여기에 시간순으로 표시되며, 엑셀(CSV) 파일로 내려받을 수 있습니다.")

elif selected_menu == "오늘 할일":
    # [메뉴 2] 오늘 할일 (제목만 표시)
    st.title("✅ 오늘 할일")

elif selected_menu == "공부회고":
    # [메뉴 3] 공부회고 (제목만 표시)
    st.title("📝 공부회고")

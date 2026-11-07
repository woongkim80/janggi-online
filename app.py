import streamlit as st
import pandas as pd
import json
import time

from janggi_engine import JanggiBoard, CHO, HAN, PIECE_CHARS, EMPTY
from janggi_ai import JanggiAI

st.set_page_config(
    page_title="핫쿠키 장기 (HOTKUKI JANGGI)",
    page_icon="🏮",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------
# 세션 상태 초기화 (로그인 불필요, AI 대전 즉시 세팅)
# -------------------------------------------------------------
if "board" not in st.session_state:
    st.session_state.board = JanggiBoard()
if "selected_pos" not in st.session_state:
    st.session_state.selected_pos = None
if "legal_moves" not in st.session_state:
    st.session_state.legal_moves = []
if "ai_player" not in st.session_state:
    st.session_state.ai_player = JanggiAI(color=HAN, difficulty="normal")
if "status_msg" not in st.session_state:
    st.session_state.status_msg = "초(楚)나라 선수의 차례입니다. 장기알을 클릭해 이동하세요."
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"sender": "시스템", "msg": "핫쿠키 AI 장기 대국실에 입장하셨습니다."},
        {"sender": "AI 상대 (한)", "msg": "좋은 한 판 부탁드립니다!"}
    ]

board: JanggiBoard = st.session_state.board

# -------------------------------------------------------------
# 핫쿠키(hotkuki.com/janggi) 오리지널 CSS 스타일
# -------------------------------------------------------------
st.markdown("""
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@700;900&family=Black+Han+Sans&display=swap">
<style>
    /* 전체 배경 */
    .stApp {
        background-color: #FBF4E4;
        color: #2E2116;
        font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
    }
    header[data-testid="stHeader"] {
        display: none;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1240px;
    }

    /* 1. 상단 내비게이션 바 */
    .hk-navbar {
        background: repeating-linear-gradient(92deg, #ffffff06 0 2px, transparent 2px 7px, #0000000a 7px 9px, transparent 9px 15px), 
                    linear-gradient(180deg, #5E3B20, #4A2C17 40%, #2E1A0C);
        box-shadow: inset 0 1px 0 #ffe2962e, inset 0 -2px 0 #D9A84A, inset 0 -4px 0 #2E1A0C, 0 6px 14px -8px #00000099;
        border-radius: 12px;
        padding: 8px 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 14px;
    }
    .hk-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        color: #FFE08A;
        font-family: 'Black Han Sans', sans-serif;
        font-size: 1.45rem;
        text-shadow: 0 2px #1F130A;
        text-decoration: none;
    }
    .hk-logo-badge {
        width: 34px;
        height: 34px;
        border-radius: 999px;
        background: radial-gradient(circle at 35% 30%, #FF7A59, #D4351C);
        color: #FFF;
        display: grid;
        place-items: center;
        box-shadow: 0 2px #7A1A05, inset 0 2px #FFFFFF59, 0 0 0 2px #FFE29680;
        font-size: 1.1rem;
        font-weight: 900;
    }
    .hk-nav-pill {
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid #D9A84A66;
        color: #F5E6C8;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 700;
    }

    /* 2. 대국자 프로필 카드 */
    .jg-profile-card {
        border-radius: 10px;
        padding: 9px 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: inset 0 0 0 1px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 8px;
    }
    .jg-profile-han {
        background: linear-gradient(135deg, #F8E1DC 0%, #FFFFFF 100%);
        border-left: 6px solid #C42A22;
    }
    .jg-profile-cho {
        background: linear-gradient(135deg, #DFE7F6 0%, #FFFFFF 100%);
        border-left: 6px solid #1E4596;
    }
    .jg-side-title {
        font-family: 'Noto Serif KR', serif;
        font-weight: 900;
        font-size: 1.15rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .jg-chip-han {
        background: #C42A22;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .jg-chip-cho {
        background: #1E4596;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }

    /* 3. 장기판 외곽 원목 프레임 */
    .jg-wood-frame {
        background: repeating-linear-gradient(90deg, #ffdcaa0d 0 2px, transparent 2px 11px, #0000000f 11px 13px, transparent 13px 23px), 
                    linear-gradient(135deg, #8E5A2F, #6B4628 40%, #4A2F1A);
        border-radius: 14px;
        padding: 10px;
        box-shadow: inset 0 2px #ffdcaa73, inset 0 -2px #00000080, 0 4px #2E1A0C, 0 20px 35px -10px rgba(40,24,10,0.6);
        border: 1px solid #3A2413;
        margin-bottom: 8px;
    }

    /* 장기판 한지 판면 */
    .jg-board-surface {
        background: radial-gradient(ellipse at 40% 35%, #EDCB86, #D9B068 70%, #C99D57);
        border: 2px solid #3C1E08;
        border-radius: 6px;
        padding: 6px 4px;
        box-shadow: inset 0 0 0 1px #3C1E0880, inset 0 3px 8px rgba(60,30,8,0.35);
    }

    /* 장기판 격자 컬럼 간격 최소화 */
    div[data-testid="column"] {
        padding: 0 1px !important;
    }

    /* 장기알 버튼 컴팩트 스타일 */
    div[data-testid="stButton"] > button {
        height: 48px !important;
        min-height: 48px !important;
        border-radius: 6px !important;
        font-family: 'Noto Serif KR', serif !important;
        font-weight: 900 !important;
        font-size: 1.15rem !important;
        padding: 0 !important;
        margin: 0 !important;
        transition: all 0.12s ease-in-out;
    }

    /* 선택된 기물 강조 */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: #FDE047 !important;
        color: #854D0E !important;
        border: 2px solid #EAB308 !important;
        box-shadow: 0 0 12px #FACC15 !important;
        transform: translateY(-2px);
    }

    /* 우측 패널 카드 */
    .hk-panel-card {
        background: #FFFDF7;
        border: 1px solid #D8C29A;
        border-radius: 10px;
        padding: 14px;
        box-shadow: 0 4px 10px rgba(90,59,34,0.08);
        margin-bottom: 12px;
    }
    .hk-panel-title {
        font-family: 'Noto Serif KR', serif;
        font-weight: 900;
        color: #5A3B22;
        border-bottom: 2px solid #D8C29A;
        padding-bottom: 6px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 1. 핫쿠키 상단 헤더 바
# -------------------------------------------------------------
st.markdown(f"""
<div class="hk-navbar">
    <a href="#" class="hk-brand">
        <div class="hk-logo-badge">장</div>
        <span>HOTKUKI 장기</span>
    </a>
    <div style="display:flex; align-items:center; gap:10px;">
        <span class="hk-nav-pill">👤 나 (초 楚) vs 🤖 AI (한 漢)</span>
        <span class="hk-nav-pill" style="background:#E0661F; color:white; border:none;">● AI 대전 모드</span>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. 메인 대국 영역 (좌: 장기판 / 우: 조작 & 훈수 패널)
# -------------------------------------------------------------
col_board_main, col_info_panel = st.columns([65, 35])

scores = board.calculate_scores()

with col_board_main:
    # 한(漢) AI 상대방 프로필 카드
    st.markdown(f"""
    <div class="jg-profile-card jg-profile-han">
        <div class="jg-side-title">
            <span class="jg-chip-han">한 漢</span>
            <span>컴퓨터 인공지능 (AI)</span>
        </div>
        <div style="font-weight:900; font-size:1.3rem; color:#C42A22;">
            {scores['HAN']}점 <span style="font-size:0.8rem; color:#8A7058;">(덤 1.5)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 클릭 핸들러 함수
    def handle_click(r: int, c: int):
        selected = st.session_state.selected_pos
        piece = board.get_piece(r, c)
        piece_color = board.get_color(piece)

        # 1. 목표 지점 클릭 (기물 이동 실행)
        if selected is not None:
            sr, sc = selected
            if (r, c) in st.session_state.legal_moves:
                moved_piece = board.get_piece(sr, sc)
                p_char = PIECE_CHARS[abs(moved_piece)][0 if moved_piece > 0 else 1]
                if board.make_move((sr, sc), (r, c)):
                    st.session_state.status_msg = f"초(楚) 착수: {p_char} ({sr},{sc}) ➔ ({r},{c})"
                    st.session_state.selected_pos = None
                    st.session_state.legal_moves = []

                    # AI 즉시 자동 응수 (한 漢)
                    if board.turn == HAN:
                        ai_mv = st.session_state.ai_player.select_best_move(board)
                        if ai_mv:
                            ai_from, ai_to = ai_mv
                            ai_p = board.get_piece(ai_from[0], ai_from[1])
                            ai_char = PIECE_CHARS[abs(ai_p)][1]
                            board.make_move(ai_from, ai_to)
                            st.session_state.status_msg = f"한(漢) AI 응수: {ai_char} ({ai_from[0]},{ai_from[1]}) ➔ ({ai_to[0]},{ai_to[1]})"
                        else:
                            board.pass_turn()
                            st.session_state.status_msg = "한(漢) AI가 둘 수가 없어 한수 쉬었습니다."
                return
            elif (r, c) == (sr, sc):
                # 동일 기물 다시 클릭 시 선택 해제
                st.session_state.selected_pos = None
                st.session_state.legal_moves = []
                return

        # 2. 내 기물 선택
        if piece != EMPTY and piece_color == board.turn:
            st.session_state.selected_pos = (r, c)
            st.session_state.legal_moves = board.get_legal_moves(r, c)
            p_char = PIECE_CHARS[abs(piece)][0 if piece > 0 else 1]
            st.session_state.status_msg = f"{p_char} 선택됨. 이동할 위치를 클릭하세요."
        else:
            st.session_state.selected_pos = None
            st.session_state.legal_moves = []

    # 장기판 본체 렌더링
    st.markdown('<div class="jg-wood-frame"><div class="jg-board-surface">', unsafe_allow_html=True)
    for r in range(10):
        cols = st.columns(9)
        for c in range(9):
            p = board.board[r][c]
            is_sel = (st.session_state.selected_pos == (r, c))
            is_legal = ((r, c) in st.session_state.legal_moves)

            if p != EMPTY:
                p_char = PIECE_CHARS[abs(p)][0 if p > 0 else 1]
                icon = "🔵" if p > 0 else "🔴"
                btn_label = f"{icon}{p_char}"
            else:
                if is_legal:
                    btn_label = "🟢"
                else:
                    btn_label = "┼"

            with cols[c]:
                st.button(
                    btn_label,
                    key=f"sq_{r}_{c}",
                    type="primary" if is_sel else "secondary",
                    use_container_width=True,
                    on_click=handle_click,
                    args=(r, c)
                )
    st.markdown('</div></div>', unsafe_allow_html=True)

    # 초(楚) 플레이어 프로필 카드
    st.markdown(f"""
    <div class="jg-profile-card jg-profile-cho">
        <div class="jg-side-title">
            <span class="jg-chip-cho">초 楚</span>
            <span>나 (플레이어)</span>
        </div>
        <div style="font-weight:900; font-size:1.3rem; color:#1E4596;">
            {scores['CHO']}점
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 승패 판정
    game_over, winner = board.is_game_over()
    if game_over:
        if winner == "CHO":
            st.balloons()
            st.success("🎉 대국 종료: 초(楚)나라 플레이어의 승리입니다!")
        else:
            st.error("💀 대국 종료: 한(漢)나라 AI가 승리하였습니다!")

# -------------------------------------------------------------
# 3. 우측 컨트롤 & 기보/채팅 패널
# -------------------------------------------------------------
with col_info_panel:
    # 대국 상황 알림
    st.markdown(f"""
    <div class="hk-panel-card" style="border-left:4px solid #E0661F;">
        <div style="font-size:0.85rem; color:#8A7058;">대국 현황 알림</div>
        <div style="font-weight:900; font-size:1.05rem; color:#2E2116; margin-top:3px;">
            {st.session_state.status_msg}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 대국 제어 버튼
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button("🏳️ 한수 쉼", use_container_width=True):
            board.pass_turn()
            st.session_state.selected_pos = None
            st.session_state.legal_moves = []
            st.session_state.status_msg = "한수 쉬었습니다. AI 차례입니다."
            # AI 응수
            if board.turn == HAN:
                ai_mv = st.session_state.ai_player.select_best_move(board)
                if ai_mv:
                    board.make_move(ai_mv[0], ai_mv[1])
            st.rerun()

    with col_c2:
        if st.button("🔄 새 대국 시작", use_container_width=True):
            st.session_state.board = JanggiBoard()
            st.session_state.selected_pos = None
            st.session_state.legal_moves = []
            st.session_state.status_msg = "새 대국이 시작되었습니다. 초(선수) 차례입니다."
            st.rerun()

    # AI 난이도 선택
    with st.expander("⚙️ AI 난이도 & 포진 설정", expanded=False):
        diff = st.radio("AI 난이도", ["초급 (기본 착수)", "보통 (수읽기 및 점수 우위)"], index=1)
        st.session_state.ai_player.difficulty = "easy" if "초급" in diff else "normal"

    # 착수 기보 히스토리
    st.markdown("""
    <div class="hk-panel-card">
        <div class="hk-panel-title">
            <span>📜 착수 기보</span>
        </div>
    """, unsafe_allow_html=True)
    if board.move_history:
        recent = board.move_history[-8:]
        kibo_data = []
        for idx, h in enumerate(recent, 1):
            s_name = "초(楚)" if h["turn"] == CHO else "한(漢)"
            if h.get("passed"):
                txt = "한수 쉼"
            else:
                p = h["piece"]
                p_char = PIECE_CHARS[abs(p)][0 if p > 0 else 1]
                txt = f"{p_char} ({h['from'][0]},{h['from'][1]}) ➔ ({h['to'][0]},{h['to'][1]})"
            kibo_data.append({"수": len(board.move_history)-len(recent)+idx, "진영": s_name, "착수": txt})
        st.dataframe(pd.DataFrame(kibo_data), hide_index=True, use_container_width=True)
    else:
        st.caption("아직 착수 기록이 없습니다.")
    st.markdown("</div>", unsafe_allow_html=True)

    # 훈수 & 채팅창
    st.markdown("""
    <div class="hk-panel-card">
        <div class="hk-panel-title">
            <span>💬 훈수 & 응원 메시지</span>
        </div>
    """, unsafe_allow_html=True)
    for c in st.session_state.chat_history[-5:]:
        st.markdown(f"**[{c['sender']}]**: {c['msg']}")

    with st.form("quick_chat_form", clear_on_submit=True):
        chat_msg = st.text_input("메시지 입력", placeholder="예: 좋은 수네요!")
        if st.form_submit_button("전송 ✉️", use_container_width=True):
            if chat_msg.strip():
                st.session_state.chat_history.append({"sender": "나", "msg": chat_msg.strip()})
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

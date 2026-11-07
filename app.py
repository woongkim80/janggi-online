import streamlit as st
import pandas as pd
import json
import time

from janggi_engine import JanggiBoard, CHO, HAN, PIECE_CHARS, EMPTY
from janggi_ai import JanggiAI
import database as db

db.init_db()

st.set_page_config(
    page_title="핫쿠키 장기 (HOTKUKI JANGGI)",
    page_icon="🏮",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 세션 상태
if "user" not in st.session_state:
    st.session_state.user = db.get_or_create_user("player@hotkuki.com", "장기명인", "")
if "board" not in st.session_state:
    st.session_state.board = JanggiBoard()
if "selected_pos" not in st.session_state:
    st.session_state.selected_pos = None
if "legal_moves" not in st.session_state:
    st.session_state.legal_moves = []
if "ai_player" not in st.session_state:
    st.session_state.ai_player = JanggiAI(color=HAN, difficulty="normal")
if "status_msg" not in st.session_state:
    st.session_state.status_msg = "초(楚)나라 선수 차례입니다."
if "current_room_id" not in st.session_state:
    st.session_state.current_room_id = "ROOM_101"

board: JanggiBoard = st.session_state.board

# -------------------------------------------------------------
# 핫쿠키(hotkuki.com/janggi) 오리지널 디자인 시스템 완전 이식
# -------------------------------------------------------------
st.markdown("""
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@700;900&family=Black+Han+Sans&display=swap">
<style>
    /* 전체 배경: 은은한 베이지/크림 톤 한지 질감 */
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
        max-width: 1200px;
    }

    /* 1. 핫쿠키 공식 상단 헤더 바 (.anav) */
    .hk-navbar {
        background: repeating-linear-gradient(92deg, #ffffff06 0 2px, transparent 2px 7px, #0000000a 7px 9px, transparent 9px 15px), 
                    linear-gradient(180deg, #5E3B20, #4A2C17 40%, #2E1A0C);
        box-shadow: inset 0 1px 0 #ffe2962e, inset 0 -2px 0 #D9A84A, inset 0 -4px 0 #2E1A0C, 0 6px 14px -8px #00000099;
        border-radius: 12px;
        padding: 8px 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 18px;
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
    .hk-nav-links {
        display: flex;
        align-items: center;
        gap: 14px;
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

    /* 2. 대국자 프로필 바 (.jg-setup-side) */
    .jg-profile-card {
        border-radius: 10px;
        padding: 10px 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: inset 0 0 0 1px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 10px;
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

    /* 3. 장기판 외곽 원목 프레임 (.jg-board) */
    .jg-wood-frame {
        background: repeating-linear-gradient(90deg, #ffdcaa0d 0 2px, transparent 2px 11px, #0000000f 11px 13px, transparent 13px 23px), 
                    linear-gradient(135deg, #8E5A2F, #6B4628 40%, #4A2F1A);
        border-radius: 14px;
        padding: 14px;
        box-shadow: inset 0 2px #ffdcaa73, inset 0 -2px #00000080, 0 4px #2E1A0C, 0 20px 35px -10px rgba(40,24,10,0.6);
        border: 1px solid #3A2413;
        margin: auto;
    }

    /* 장기판 한지 판면 (.jg-board-face) */
    .jg-board-surface {
        background: radial-gradient(ellipse at 40% 35%, #EDCB86, #D9B068 70%, #C99D57);
        border: 2px solid #3C1E08;
        border-radius: 6px;
        padding: 10px;
        box-shadow: inset 0 0 0 1px #3C1E0880, inset 0 3px 8px rgba(60,30,8,0.35);
    }

    /* 4. 팔각 옥돌 기물 디자인 (.jg-piece-ivory) */
    div[data-testid="stButton"] > button {
        height: 52px !important;
        border-radius: 8px !important;
        font-family: 'Noto Serif KR', serif !important;
        font-weight: 900 !important;
        font-size: 1.25rem !important;
        padding: 0 !important;
        transition: all 0.15s ease-in-out;
    }

    /* 빈 교차점 */
    div[data-testid="stButton"] > button:has(.empty-point) {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #2E211680 !important;
        font-size: 1.1rem !important;
    }

    /* 이동 가능 점 하이라이트 */
    div[data-testid="stButton"] > button:has(.legal-point) {
        background: radial-gradient(circle, #4ADE80CC 35%, transparent 40%) !important;
        border: 1px dashed #16A34A !important;
        box-shadow: 0 0 8px #22C55E80 !important;
    }

    /* 초나라 기물 (푸른색 각인) */
    div[data-testid="stButton"] > button:has(.piece-cho) {
        background: linear-gradient(150deg, #FFFFFF, #F7F3EA 45%, #DDD2BD) !important;
        color: #1E4596 !important;
        border: 2px solid #B9AE98 !important;
        box-shadow: 0 3px 0 #8A7058, 0 6px 8px rgba(40,24,10,0.3) !important;
        clip-path: polygon(29% 0, 71% 0, 100% 29%, 100% 71%, 71% 100%, 29% 100%, 0 71%, 0 29%);
        text-shadow: 0 1px #FFFFFFE6;
    }

    /* 한나라 기물 (붉은색 각인) */
    div[data-testid="stButton"] > button:has(.piece-han) {
        background: linear-gradient(150deg, #FFFFFF, #F7F3EA 45%, #DDD2BD) !important;
        color: #C42A22 !important;
        border: 2px solid #B9AE98 !important;
        box-shadow: 0 3px 0 #8A7058, 0 6px 8px rgba(40,24,10,0.3) !important;
        clip-path: polygon(29% 0, 71% 0, 100% 29%, 100% 71%, 71% 100%, 29% 100%, 0 71%, 0 29%);
        text-shadow: 0 1px #FFFFFFE6;
    }

    /* 기물 선택 시 발광 펄스 */
    div[data-testid="stButton"] > button[kind="primary"] {
        border: 2px solid #E0661F !important;
        box-shadow: 0 0 12px #F97316 !important;
        transform: translateY(-2px);
    }

    /* 5. 핫쿠키 스타일 우측 사이드 패널 (채팅 및 기보) */
    .hk-panel-card {
        background: #FFFDF7;
        border: 1px solid #D8C29A;
        border-radius: 10px;
        padding: 14px;
        box-shadow: 0 4px 10px rgba(90,59,34,0.08);
        margin-bottom: 14px;
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
# 1. 핫쿠키 상단 내비게이션 바 렌더링
# -------------------------------------------------------------
user = st.session_state.user
st.markdown(f"""
<div class="hk-navbar">
    <a href="#" class="hk-brand">
        <div class="hk-logo-badge">장</div>
        <span>HOTKUKI 장기</span>
    </a>
    <div class="hk-nav-links">
        <span class="hk-nav-pill">👑 {user['name']} ({user['rating']}점)</span>
        <span class="hk-nav-pill">🌐 방번호: {st.session_state.current_room_id}</span>
        <span class="hk-nav-pill" style="background: #E0661F; color:white; border:none;">● 실시간 대전</span>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. 메인 대국 화면 레이아웃 (좌: 장기판 / 우: 핫쿠키 컨트롤 패널)
# -------------------------------------------------------------
col_board_main, col_info_panel = st.columns([68, 32])

scores = board.calculate_scores()

with col_board_main:
    # 한(漢) 상대방 프로필 카드
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

    # 클릭 이벤트 처리 함수
    def handle_click(r: int, c: int):
        selected = st.session_state.selected_pos
        piece = board.get_piece(r, c)
        piece_color = board.get_color(piece)

        # 목표 지점 클릭 (이동 실행)
        if selected is not None:
            sr, sc = selected
            if (r, c) in st.session_state.legal_moves:
                if board.make_move((sr, sc), (r, c)):
                    st.session_state.status_msg = f"초(楚) 착수: ({sr},{sc}) ➔ ({r},{c})"
                    st.session_state.selected_pos = None
                    st.session_state.legal_moves = []

                    # 컴퓨터 응수
                    if board.turn == HAN:
                        ai_mv = st.session_state.ai_player.select_best_move(board)
                        if ai_mv:
                            board.make_move(ai_mv[0], ai_mv[1])
                            st.session_state.status_msg = f"한(漢) AI 응수: ({ai_mv[0][0]},{ai_mv[0][1]}) ➔ ({ai_mv[1][0]},{ai_mv[1][1]})"
                        else:
                            board.pass_turn()
                            st.session_state.status_msg = "한(漢) AI 한수 쉼"
                return
            elif (r, c) == (sr, sc):
                st.session_state.selected_pos = None
                st.session_state.legal_moves = []
                return

        # 내 기물 선택
        if piece != EMPTY and piece_color == board.turn:
            st.session_state.selected_pos = (r, c)
            st.session_state.legal_moves = board.get_legal_moves(r, c)
        else:
            st.session_state.selected_pos = None
            st.session_state.legal_moves = []

    # 장기판 본체 (.jg-wood-frame > .jg-board-surface)
    st.markdown('<div class="jg-wood-frame"><div class="jg-board-surface">', unsafe_allow_html=True)
    for r in range(10):
        cols = st.columns(9)
        for c in range(9):
            p = board.board[r][c]
            is_sel = (st.session_state.selected_pos == (r, c))
            is_legal = ((r, c) in st.session_state.legal_moves)

            if p != EMPTY:
                p_char = PIECE_CHARS[abs(p)][0 if p > 0 else 1]
                cls_name = "piece-cho" if p > 0 else "piece-han"
                btn_markup = f'<span class="{cls_name}">{p_char}</span>'
            else:
                if is_legal:
                    btn_markup = '<span class="legal-point">●</span>'
                else:
                    btn_markup = '<span class="empty-point">┼</span>'

            with cols[c]:
                st.button(
                    btn_markup,
                    key=f"hk_sq_{r}_{c}",
                    type="primary" if is_sel else "secondary",
                    use_container_width=True,
                    on_click=handle_click,
                    args=(r, c)
                )
    st.markdown('</div></div>', unsafe_allow_html=True)

    # 초(楚) 플레이어 프로필 카드
    st.markdown(f"""
    <div class="jg-profile-card jg-profile-cho" style="margin-top:10px;">
        <div class="jg-side-title">
            <span class="jg-chip-cho">초 楚</span>
            <span>{user['name']} (나)</span>
        </div>
        <div style="font-weight:900; font-size:1.3rem; color:#1E4596;">
            {scores['CHO']}점
        </div>
    </div>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------
# 3. 우측 컨트롤 & 관전자 훈수 패널 (핫쿠키 스타일)
# -------------------------------------------------------------
with col_info_panel:
    # 대국 상황 알림
    st.markdown(f"""
    <div class="hk-panel-card" style="border-left:4px solid #E0661F;">
        <div style="font-size:0.85rem; color:#8A7058;">대국 알림</div>
        <div style="font-weight:900; font-size:1.05rem; color:#2E2116; margin-top:2px;">
            {st.session_state.status_msg}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 대국 조작 버튼
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("🏳️ 한수 쉼", use_container_width=True):
            board.pass_turn()
            st.session_state.selected_pos = None
            st.session_state.legal_moves = []
            st.session_state.status_msg = "한수 쉬었습니다."
            st.rerun()
    with c_btn2:
        if st.button("🔄 새 대국", use_container_width=True):
            st.session_state.board = JanggiBoard()
            st.session_state.selected_pos = None
            st.session_state.legal_moves = []
            st.session_state.status_msg = "새 대국이 시작되었습니다."
            st.rerun()

    # 실시간 관전 & 훈수 채팅방
    st.markdown("""
    <div class="hk-panel-card">
        <div class="hk-panel-title">
            <span>💬 관전자 훈수 & 실시간 채팅</span>
            <span style="font-size:0.75rem; color:#16A34A;">● 3명 관전 중</span>
        </div>
    """, unsafe_allow_html=True)

    msgs = db.get_room_messages(st.session_state.current_room_id, limit=8)
    for m in msgs:
        st.markdown(f"**[{m['sender_name']}]**: {m['message']}")

    with st.form("hk_chat_form", clear_on_submit=True):
        chat_val = st.text_input("훈수 남기기", placeholder="초나라 포 배치가 절묘하네요!")
        if st.form_submit_button("전송 ✉️", use_container_width=True):
            if chat_val.strip():
                db.send_chat_message(st.session_state.current_room_id, user['name'], chat_val.strip())
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # 착수 기보 리스트
    st.markdown("""
    <div class="hk-panel-card">
        <div class="hk-panel-title">
            <span>📜 착수 기보</span>
        </div>
    """, unsafe_allow_html=True)
    if board.move_history:
        recent = board.move_history[-6:]
        kibo_data = []
        for idx, h in enumerate(recent, 1):
            s_name = "초" if h["turn"] == CHO else "한"
            txt = "한수 쉼" if h.get("passed") else f"{PIECE_CHARS[abs(h['piece'])][0 if h['piece']>0 else 1]} ({h['from'][0]},{h['from'][1]})➔({h['to'][0]},{h['to'][1]})"
            kibo_data.append({"수": len(board.move_history)-len(recent)+idx, "진영": s_name, "착수": txt})
        st.dataframe(pd.DataFrame(kibo_data), hide_index=True, use_container_width=True)
    else:
        st.caption("착수 기록이 없습니다.")
    st.markdown("</div>", unsafe_allow_html=True)

import streamlit as st
import pandas as pd
import json
import time
from typing import Optional

from janggi_engine import JanggiBoard, CHO, HAN, PIECE_CHARS, EMPTY
from janggi_ai import JanggiAI
import database as db

# DB 초기화
db.init_db()

st.set_page_config(
    page_title="천하명인 온라인 장기 (Janggi Online)",
    page_icon="♟️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# 세션 상태 관리
# -------------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None  # 로그인 사용자 정보
if "current_room_id" not in st.session_state:
    st.session_state.current_room_id = "AI_PRACTICE"
if "board" not in st.session_state:
    st.session_state.board = JanggiBoard()
if "selected_pos" not in st.session_state:
    st.session_state.selected_pos = None
if "legal_moves" not in st.session_state:
    st.session_state.legal_moves = []
if "ai_player" not in st.session_state:
    st.session_state.ai_player = JanggiAI(color=HAN, difficulty="normal")
if "status_msg" not in st.session_state:
    st.session_state.status_msg = "초(楚)나라 선수의 차례입니다."
if "user_role" not in st.session_state:
    st.session_state.user_role = "PLAYER_CHO"  # PLAYER_CHO, PLAYER_HAN, SPECTATOR

board: JanggiBoard = st.session_state.board

# -------------------------------------------------------------
# 커스텀 CSS (고급 원목 질감 + 한자 각인 장기알)
# -------------------------------------------------------------
st.markdown("""
<style>
    .janggi-board-table {
        background: radial-gradient(circle, #F3D9A4 0%, #D8A562 100%);
        border: 4px solid #6E4018;
        border-radius: 12px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.25);
        padding: 12px;
        margin: auto;
    }
    .score-banner {
        background: #FFFFFF;
        border-radius: 10px;
        border: 1px solid #E2E8F0;
        padding: 10px 16px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
    }
    .chat-box {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 10px;
        height: 280px;
        overflow-y: auto;
        font-size: 0.9rem;
    }
    .chat-player {
        color: #2563EB;
        font-weight: 600;
    }
    .chat-spec {
        color: #64748B;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 사이드바: 1. 구글 간편 로그인 & 프로필
# -------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/google-logo.png", width=36)
    st.title("구글 로그인 & 프로필")

    if not st.session_state.user:
        st.write("구글 계정으로 로그인하여 온라인 대전과 전적 랭킹에 참여하세요.")
        with st.form("google_login_form"):
            g_email = st.text_input("구글 이메일", value="master_player@gmail.com")
            g_name = st.text_input("대국명(닉네임)", value="장기명인 9단")
            if st.form_submit_button("🚀 구글 계정으로 1초 로그인", type="primary", use_container_width=True):
                st.session_state.user = db.get_or_create_user(email=g_email, name=g_name)
                st.success(f"환영합니다, {g_name}님!")
                st.rerun()
    else:
        user = st.session_state.user
        st.markdown(f"**접속자:** `{user['name']}` ({user['email']})")
        c1, c2, c3 = st.columns(3)
        c1.metric("레이팅", f"{user['rating']}점")
        c2.metric("승/패", f"{user['wins']}승 {user['losses']}패")
        c3.metric("승률", f"{(user['wins']/(user['wins']+user['losses'])*100):.0f}%" if (user['wins']+user['losses']) > 0 else "신규")

        if st.button("로그아웃", use_container_width=True):
            st.session_state.user = None
            st.rerun()

    st.divider()

    # -------------------------------------------------------------
    # 사이드바: 2. 실시간 대전방 및 관전(Spectator) 선택
    # -------------------------------------------------------------
    st.subheader("🌐 실시간 대전 & 관전 룸")
    active_rooms = db.list_active_rooms()

    room_options = ["🤖 [연습] 컴퓨터(AI) 대전"] + [f"🏠 {r['title']} (#{r['room_id']})" for r in active_rooms]
    selected_room_label = st.selectbox("참여할 대국방 선택", room_options)

    if selected_room_label.startswith("🤖"):
        st.session_state.current_room_id = "AI_PRACTICE"
        st.session_state.user_role = "PLAYER_CHO"
    else:
        # 방 번호 추출
        sel_rid = selected_room_label.split("(#")[1].replace(")", "")
        st.session_state.current_room_id = sel_rid

    # 신규 방 만들기
    with st.expander("➕ 새 대전방 개설하기"):
        new_title = st.text_input("방 제목", value="누구나 환영 1:1 진검승부")
        new_id = f"R{int(time.time())%10000}"
        if st.button("방 개설하기", type="primary", use_container_width=True):
            creator = st.session_state.user['name'] if st.session_state.user else "초청대국자"
            db.create_or_join_room(room_id=new_id, title=new_title, player_name=creator, side="CHO")
            st.session_state.current_room_id = new_id
            st.session_state.user_role = "PLAYER_CHO"
            st.success(f"대국방 #{new_id}가 생성되었습니다!")
            st.rerun()

    st.divider()
    st.subheader("⚙️ 포진 및 대국 설정")
    cho_form = st.selectbox("초(선수) 차림", ["MSMS (마상마상)", "SMSM (상마상마)", "MSSM (마상상마)", "SMMS (상마마상)"])
    han_form = st.selectbox("한(후수) 차림", ["MSMS (마상마상)", "SMSM (상마상마)", "MSSM (마상상마)", "SMMS (상마마상)"])

    if st.button("🔄 판 초기화 / 새 대국", use_container_width=True):
        st.session_state.board = JanggiBoard(cho_form[:4], han_form[:4])
        st.session_state.selected_pos = None
        st.session_state.legal_moves = []
        st.session_state.status_msg = "초(楚)나라 선수의 차례입니다."
        st.rerun()

    if st.button("🏳️ 한수 쉼 (Pass)", use_container_width=True):
        board.pass_turn()
        st.session_state.selected_pos = None
        st.session_state.legal_moves = []
        st.session_state.status_msg = f"{'초(楚)' if board.turn == CHO else '한(漢)'}에게 차례가 넘어갔습니다."
        st.rerun()

# -------------------------------------------------------------
# 메인 영역 레이아웃 (좌: 장기판 / 우: 실시간 관전 & 훈수 채팅)
# -------------------------------------------------------------
main_col_board, main_col_panel = st.columns([7, 3])

# 점수 계산
scores = board.calculate_scores()

with main_col_board:
    st.title("🏆 천하명인 장기 (온라인 실시간 대전 & 관전)")

    # 상단 점수 배너
    b_col1, b_col2, b_col3 = st.columns([4, 2, 4])
    with b_col1:
        st.markdown(f"""
        <div class="score-banner" style="border-left: 5px solid #EF4444;">
            <span style="color:#DC2626; font-weight:700;">🔴 한(漢)</span> [후수]
            <h3 style="margin:2px 0 0 0; color:#1E293B;">{scores['HAN']}점</h3>
        </div>
        """, unsafe_allow_html=True)
    with b_col2:
        turn_txt = "🔵 초(楚) 차례" if board.turn == CHO else "🔴 한(漢) 차례"
        st.markdown(f"<div style='text-align:center; padding-top:14px;'><h4>{turn_txt}</h4></div>", unsafe_allow_html=True)
    with b_col3:
        st.markdown(f"""
        <div class="score-banner" style="border-left: 5px solid #2563EB;">
            <span style="color:#2563EB; font-weight:700;">🔵 초(楚)</span> [선수]
            <h3 style="margin:2px 0 0 0; color:#1E293B;">{scores['CHO']}점</h3>
        </div>
        """, unsafe_allow_html=True)

    st.info(f"📢 **대국 상황:** {st.session_state.status_msg}")

    # -------------------------------------------------------------
    # 장기판 클릭 핸들러
    # -------------------------------------------------------------
    def on_board_click(r: int, c: int):
        selected = st.session_state.selected_pos
        piece = board.get_piece(r, c)
        piece_color = board.get_color(piece)

        # 1. 이동 실행
        if selected is not None:
            sr, sc = selected
            if (r, c) in st.session_state.legal_moves:
                success = board.make_move((sr, sc), (r, c))
                if success:
                    st.session_state.status_msg = f"착수: ({sr},{sc}) ➔ ({r},{c})"
                    st.session_state.selected_pos = None
                    st.session_state.legal_moves = []

                    # AI 대전 모드일 때 자동 응수
                    if st.session_state.current_room_id == "AI_PRACTICE" and board.turn == HAN:
                        ai_move = st.session_state.ai_player.select_best_move(board)
                        if ai_move:
                            a_from, a_to = ai_move
                            board.make_move(a_from, a_to)
                            st.session_state.status_msg = f"🤖 컴퓨터 응수: ({a_from[0]},{a_from[1]}) ➔ ({a_to[0]},{a_to[1]})"
                        else:
                            board.pass_turn()
                            st.session_state.status_msg = "🤖 컴퓨터 한수 쉼"
                return
            elif (r, c) == (sr, sc):
                st.session_state.selected_pos = None
                st.session_state.legal_moves = []
                return

        # 2. 기물 선택
        if piece != EMPTY and piece_color == board.turn:
            st.session_state.selected_pos = (r, c)
            st.session_state.legal_moves = board.get_legal_moves(r, c)
            st.session_state.status_msg = f"기물 선택됨: {PIECE_CHARS[abs(piece)][0 if piece>0 else 1]} (이동 가능 {len(st.session_state.legal_moves)}곳)"
        else:
            st.session_state.selected_pos = None
            st.session_state.legal_moves = []

    # -------------------------------------------------------------
    # 9 x 10 보드 렌더링
    # -------------------------------------------------------------
    st.markdown('<div class="janggi-board-table">', unsafe_allow_html=True)
    for r in range(10):
        cols = st.columns(9)
        for c in range(9):
            p = board.board[r][c]
            is_sel = (st.session_state.selected_pos == (r, c))
            is_legal = ((r, c) in st.session_state.legal_moves)

            if p != EMPTY:
                p_type = abs(p)
                p_char = PIECE_CHARS[p_type][0 if p > 0 else 1]
                icon = "🔵" if p > 0 else "🔴"
                label = f"{icon}{p_char}"
            else:
                label = "🟢" if is_legal else "┼"

            b_type = "primary" if is_sel else "secondary"

            with cols[c]:
                st.button(
                    label,
                    key=f"b_{r}_{c}",
                    type=b_type,
                    use_container_width=True,
                    on_click=on_board_click,
                    args=(r, c)
                )
    st.markdown('</div>', unsafe_allow_html=True)

    # 승패 판정
    game_over, winner = board.is_game_over()
    if game_over:
        if winner == "CHO":
            st.balloons()
            st.success("🎉 대국 종료: 초(楚)나라 승리!")
            if st.session_state.user:
                db.update_user_record(st.session_state.user['email'], is_win=True)
        else:
            st.error("💀 대국 종료: 한(漢)나라 승리!")
            if st.session_state.user:
                db.update_user_record(st.session_state.user['email'], is_win=False)

# -------------------------------------------------------------
# 우측 패널: 실시간 관전자 훈수 & 채팅방
# -------------------------------------------------------------
with main_col_panel:
    st.subheader(f"💬 관전 & 훈수 ({st.session_state.current_room_id})")

    # 채팅 메시지 목록 불러오기
    messages = db.get_room_messages(st.session_state.current_room_id, limit=15)
    
    chat_html = '<div class="chat-box">'
    if not messages:
        chat_html += '<p style="color:#94A3B8; text-align:center;">첫 번째 훈수 또는 응원 메시지를 남겨보세요!</p>'
    for m in messages:
        sender_cls = "chat-player" if m["is_player"] else "chat-spec"
        chat_html += f'<div><span class="{sender_cls}">[{m["sender_name"]}]:</span> {m["message"]}</div>'
    chat_html += '</div>'
    st.markdown(chat_html, unsafe_allow_html=True)

    # 채팅 입력창
    with st.form("chat_input_form", clear_on_submit=True):
        chat_input = st.text_input("메시지 입력", placeholder="예: 초나라 차가 치고 나가면 유리하네요!")
        if st.form_submit_button("전송 ✉️", use_container_width=True):
            if chat_input.strip():
                sender = st.session_state.user['name'] if st.session_state.user else "익명관전자"
                db.send_chat_message(
                    room_id=st.session_state.current_room_id,
                    sender_name=sender,
                    message=chat_input.strip(),
                    is_player=1 if st.session_state.user_role.startswith("PLAYER") else 0
                )
                st.rerun()

    st.divider()
    st.subheader("📜 착수 기보 (Move History)")
    if board.move_history:
        history_df = []
        for idx, h in enumerate(board.move_history[-10:], 1):
            t_name = "초(楚)" if h["turn"] == CHO else "한(漢)"
            if h.get("passed"):
                mv_str = "한수 쉼"
            else:
                p_name = PIECE_CHARS[abs(h["piece"])][0 if h["piece"]>0 else 1]
                mv_str = f"{p_name} ({h['from'][0]},{h['from'][1]}) ➔ ({h['to'][0]},{h['to'][1]})"
            history_df.append({"순번": len(board.move_history) - 10 + idx, "진영": t_name, "착수": mv_str})
        st.dataframe(pd.DataFrame(history_df), hide_index=True, use_container_width=True)
    else:
        st.caption("아직 착수 기록이 없습니다.")

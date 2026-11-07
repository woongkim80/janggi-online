import streamlit as st
import json
import time

from janggi_engine import JanggiBoard, CHO, HAN, PIECE_CHARS, EMPTY
from janggi_ai import JanggiAI
import database as db

# SQLite 데이터베이스 초기화
db.init_db()

st.set_page_config(
    page_title="AI 온라인 장기 (mimmi.co.kr 스타일)",
    page_icon="♟️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------
# 세션 상태 관리 (순수 Streamlit 인터랙션)
# -------------------------------------------------------------
if "game_id" not in st.session_state:
    st.session_state.game_id = f"GAME_{int(time.time())}"
if "board" not in st.session_state:
    st.session_state.board = JanggiBoard()
if "ai_player" not in st.session_state:
    st.session_state.ai_player = JanggiAI(color=HAN, difficulty="normal")
if "selected_pos" not in st.session_state:
    st.session_state.selected_pos = None
if "legal_moves" not in st.session_state:
    st.session_state.legal_moves = []
if "status_banner" not in st.session_state:
    st.session_state.status_banner = "당신(초)의 차례입니다."

board: JanggiBoard = st.session_state.board
scores = board.calculate_scores()
game_over, winner = board.is_game_over()

# -------------------------------------------------------------
# mimmi.co.kr 오리지널 스타일 CSS 정의
# -------------------------------------------------------------
st.markdown("""
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@700;900&display=swap">
<style>
    /* 전체 배경: mimmi.co.kr 다크 네이비 톤 */
    .stApp {
        background-color: #111827;
        color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
    }
    header[data-testid="stHeader"] {
        display: none;
    }
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    /* 상단 상태 배너 (첨부 이미지 스타일) */
    .status-banner {
        background: #0f172a;
        border: 1px solid #1e293b;
        color: #f1f5f9;
        font-weight: 700;
        font-size: 16px;
        padding: 10px 24px;
        border-radius: 8px;
        margin-bottom: 12px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.4);
    }

    /* 장기판 원목 배경 컨테이너 */
    .janggi-board-table {
        background-color: #E5A358;
        border-radius: 14px;
        padding: 12px 10px;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.7), inset 0 0 0 2px #3c2411;
        margin: auto;
    }

    /* 컬럼 간격 최소화 */
    div[data-testid="column"] {
        padding: 0 1px !important;
    }

    /* 장기판 버튼 기본 스타일 (정사각형에 가까운 크기) */
    div[data-testid="stButton"] > button {
        height: 52px !important;
        min-height: 52px !important;
        border-radius: 6px !important;
        font-family: '궁서', 'Gungsuh', 'Noto Serif KR', serif !important;
        font-weight: 900 !important;
        font-size: 1.25rem !important;
        padding: 0 !important;
        margin: 0 !important;
        transition: all 0.12s ease-in-out;
        border: none !important;
    }

    /* 1. 빈 교차점 (┼) */
    div[data-testid="stButton"] > button:has(.empty-point) {
        background: transparent !important;
        color: #3b200b80 !important;
        font-size: 1.05rem !important;
        box-shadow: none !important;
    }
    div[data-testid="stButton"] > button:has(.empty-point):hover {
        background: rgba(0,0,0,0.05) !important;
    }

    /* 2. 이동 가능한 위치 힌트 점 (녹색 원) */
    div[data-testid="stButton"] > button:has(.legal-point) {
        background: transparent !important;
        box-shadow: none !important;
    }
    .legal-dot {
        display: inline-block;
        width: 15px;
        height: 15px;
        background-color: #10B981;
        border: 2px solid #047857;
        border-radius: 50%;
        box-shadow: 0 0 8px #10B981;
    }

    /* 3. 상대 기물 잡기 가능 위치 (붉은 타겟 링) */
    div[data-testid="stButton"] > button:has(.capture-target) {
        background: rgba(239, 68, 68, 0.25) !important;
        box-shadow: inset 0 0 0 3px #EF4444 !important;
    }

    /* 4. 팔각 옥돌 기물 (초나라: 녹색 테두리 + 녹색 한자) */
    .piece-cho {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 44px;
        height: 44px;
        margin: auto;
        background: #FACC15;
        color: #047857;
        clip-path: polygon(30% 0%, 70% 0%, 100% 30%, 100% 70%, 70% 100%, 30% 100%, 0% 70%, 0% 30%);
        border: 2px solid #047857;
        box-shadow: 0 3px 0 #8A7058;
        font-size: 1.25rem;
    }

    /* 5. 팔각 옥돌 기물 (한나라: 붉은 테두리 + 붉은 한자) */
    .piece-han {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 44px;
        height: 44px;
        margin: auto;
        background: #FACC15;
        color: #C62828;
        clip-path: polygon(30% 0%, 70% 0%, 100% 30%, 100% 70%, 70% 100%, 30% 100%, 0% 70%, 0% 30%);
        border: 2px solid #C62828;
        box-shadow: 0 3px 0 #8A7058;
        font-size: 1.25rem;
    }

    /* 선택된 기물 하이라이트 (파란 테두리 발광) */
    div[data-testid="stButton"] > button[kind="primary"] {
        box-shadow: 0 0 12px #3B82F6, inset 0 0 0 3px #2563EB !important;
        transform: translateY(-2px);
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 클릭 이벤트 핸들러: 이동 경로 보기 & 클릭 시 즉각 이동 & DB 저장
# -------------------------------------------------------------
def on_square_clicked(r: int, c: int):
    selected = st.session_state.selected_pos
    piece = board.get_piece(r, c)
    piece_color = board.get_color(piece)

    # [동작 2] 이미 기물이 선택되어 있고, 클릭한 좌표가 이동 가능 경로인 경우 -> 착수 & DB 저장!
    if selected is not None:
        sr, sc = selected
        if (r, c) in st.session_state.legal_moves:
            moved_p = board.get_piece(sr, sc)
            cap_p = board.get_piece(r, c)
            p_name = PIECE_CHARS[abs(moved_p)][0] if moved_p > 0 else "기물"
            cap_name = PIECE_CHARS[abs(cap_p)][1] if cap_p != EMPTY else ""

            # 1. 플레이어 착수 실행
            if board.make_move((sr, sc), (r, c)):
                st.session_state.status_banner = f"초(楚) 착수: {p_name} ({sr},{sc}) ➔ ({r},{c})"
                st.session_state.selected_pos = None
                st.session_state.legal_moves = []

                # SQLite DB 저장
                db.save_move_record(
                    game_id=st.session_state.game_id,
                    move_no=len(board.move_history),
                    turn_side="CHO",
                    piece_name=p_name,
                    from_pos=(sr, sc),
                    to_pos=(r, c),
                    captured_name=cap_name,
                    fen_str=json.dumps(board.board)
                )

                # 2. 상대 컴퓨터 AI (한 漢) 자동 응수
                if board.turn == HAN:
                    ai_mv = st.session_state.ai_player.select_best_move(board)
                    if ai_mv:
                        ai_fr, ai_to = ai_mv
                        ai_p = board.get_piece(ai_fr[0], ai_fr[1])
                        ai_cap = board.get_piece(ai_to[0], ai_to[1])
                        ai_p_name = PIECE_CHARS[abs(ai_p)][1] if ai_p != EMPTY else "기물"
                        ai_cap_name = PIECE_CHARS[abs(ai_cap)][0] if ai_cap != EMPTY else ""

                        board.make_move(ai_fr, ai_to)
                        # AI 착수도 DB에 저장!
                        db.save_move_record(
                            game_id=st.session_state.game_id,
                            move_no=len(board.move_history),
                            turn_side="HAN",
                            piece_name=ai_p_name,
                            from_pos=ai_fr,
                            to_pos=ai_to,
                            captured_name=ai_cap_name,
                            fen_str=json.dumps(board.board)
                        )
                        st.session_state.status_banner = f"한(漢) AI 응수: {ai_p_name} ({ai_fr[0]},{ai_fr[1]}) ➔ ({ai_to[0]},{ai_to[1]})"
                    else:
                        board.pass_turn()
                        st.session_state.status_banner = "한(漢) AI가 둘 수가 없어 한수 쉬었습니다."
            return
        elif (r, c) == (sr, sc):
            # 동일 기물 다시 누르면 선택 해제
            st.session_state.selected_pos = None
            st.session_state.legal_moves = []
            st.session_state.status_banner = "당신(초)의 차례입니다."
            return

    # [동작 1] 내 기물(초나라 p > 0)을 누르면 이동 경로 보기 활성화
    if piece != EMPTY and piece_color == board.turn:
        st.session_state.selected_pos = (r, c)
        st.session_state.legal_moves = board.get_legal_moves(r, c)
        p_name = PIECE_CHARS[abs(piece)][0 if piece > 0 else 1]
        st.session_state.status_banner = f"{p_name} 선택됨 (이동 가능 경로 {len(st.session_state.legal_moves)}곳 표시)"
    else:
        st.session_state.selected_pos = None
        st.session_state.legal_moves = []
        st.session_state.status_banner = "당신(초)의 차례입니다."

# -------------------------------------------------------------
# 메인 레이아웃: 장기판 & 기보/조작 패널
# -------------------------------------------------------------
col_l, col_board, col_history = st.columns([1, 6, 3])

with col_board:
    # 상단 상태 배너
    banner_txt = st.session_state.status_banner
    if game_over:
        banner_txt = "🎉 대국 종료: 초(楚) 승리!" if winner == "CHO" else "💀 대국 종료: 한(漢) 승리!"
    st.markdown(f'<div class="status-banner">{banner_txt}</div>', unsafe_allow_html=True)

    # 장기판 테이블 렌더링
    st.markdown('<div class="janggi-board-table">', unsafe_allow_html=True)
    for r in range(10):
        cols = st.columns(9)
        for c in range(9):
            p = board.board[r][c]
            is_sel = (st.session_state.selected_pos == (r, c))
            is_legal = ((r, c) in st.session_state.legal_moves)

            if p != EMPTY:
                p_char = PIECE_CHARS[abs(p)][0 if p > 0 else 1]
                cls = "piece-cho" if p > 0 else "piece-han"
                if is_legal:
                    # 상대 기물을 잡을 수 있는 위치
                    btn_markup = f'<div class="{cls} capture-target">{p_char}</div>'
                else:
                    btn_markup = f'<div class="{cls}">{p_char}</div>'
            else:
                if is_legal:
                    # 이동 가능한 위치: 녹색 원 표시
                    btn_markup = '<div class="legal-point"><span class="legal-dot"></span></div>'
                else:
                    btn_markup = '<span class="empty-point">┼</span>'

            with cols[c]:
                st.button(
                    btn_markup,
                    key=f"sq_{r}_{c}",
                    type="primary" if is_sel else "secondary",
                    use_container_width=True,
                    on_click=on_square_clicked,
                    args=(r, c)
                )
    st.markdown('</div>', unsafe_allow_html=True)

with col_history:
    st.markdown("### 📜 대국 기보 & 조작")
    st.caption(f"대국 ID: `{st.session_state.game_id}` • SQLite 실시간 저장")

    s1, s2 = st.columns(2)
    with s1:
        st.metric("🔵 초 (나)", f"{scores['CHO']}점")
    with s2:
        st.metric("🔴 한 (AI)", f"{scores['HAN']}점")

    # 되돌리기(무르기) & 새 대국 버튼
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        can_undo = len(board.move_history) > 0
        if st.button("⏪ 한수 무르기", use_container_width=True, disabled=not can_undo):
            # AI 1수 + 내 1수 = 총 2수 무르기
            if len(board.move_history) >= 2:
                board.undo_move()
                board.undo_move()
                db.undo_last_move_record(st.session_state.game_id, count=2)
            elif len(board.move_history) == 1:
                board.undo_move()
                db.undo_last_move_record(st.session_state.game_id, count=1)
            st.session_state.selected_pos = None
            st.session_state.legal_moves = []
            st.session_state.status_banner = "이전 수로 되돌렸습니다. 당신(초)의 차례입니다."
            st.rerun()

    with btn_col2:
        if st.button("🔄 새 대국", use_container_width=True, type="primary"):
            st.session_state.game_id = f"GAME_{int(time.time())}"
            st.session_state.board = JanggiBoard()
            st.session_state.selected_pos = None
            st.session_state.legal_moves = []
            st.session_state.status_banner = "새 대국이 시작되었습니다. 당신(초)의 차례입니다."
            st.rerun()

    # DB에 영구 저장된 착수 기록 실시간 조회
    moves = db.get_game_moves(st.session_state.game_id)
    if moves:
        df_list = []
        for m in moves:
            badge = "🔵 초" if m["turn"] == "CHO" else "🔴 한"
            desc = f"{m['piece_type']} ({m['from_r']},{m['from_c']}) ➔ ({m['to_r']},{m['to_c']})"
            if m["captured"]:
                desc += f" (잡음: {m['captured']})"
            df_list.append({
                "수": m["move_number"],
                "진영": badge,
                "착수": desc,
                "시각": m["created_at"].split()[1]
            })
        st.dataframe(pd.DataFrame(df_list), hide_index=True, use_container_width=True, height=440)
    else:
        st.info("💡 **이동 방법**: 장기알을 클릭하면 이동 가능한 위치에 **녹색 원(🟢)**이 표시됩니다. 녹색 원을 마우스로 누르면 말이 즉시 이동하고 DB에 저장됩니다.")

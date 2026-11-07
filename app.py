import streamlit as st
import json
import time
import os

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
# 세션 상태 관리
# -------------------------------------------------------------
if "game_id" not in st.session_state:
    st.session_state.game_id = f"GAME_{int(time.time())}"
if "board" not in st.session_state:
    st.session_state.board = JanggiBoard()
if "ai_player" not in st.session_state:
    st.session_state.ai_player = JanggiAI(color=HAN, difficulty="normal")

board: JanggiBoard = st.session_state.board

# -------------------------------------------------------------
# API 엔드포인트: 프론트엔드 JS에서 즉시 착수 저장 요청 처리
# -------------------------------------------------------------
# 로컬 JSON 파일 기반 비동기 브릿지 및 세션 동기화
BRIDGE_FILE = os.path.join(os.path.dirname(__file__), "last_move.json")

# URL 쿼리 파라미터 또는 POST 브릿지 확인
qp = st.query_params
if "save_move" in qp:
    mv_str = qp["save_move"]
    del st.query_params["save_move"]
    if "t" in qp:
        del st.query_params["t"]
    try:
        r1, c1, r2, c2 = map(int, mv_str.split(","))
        moved_p = board.get_piece(r1, c1)
        cap_p = board.get_piece(r2, c2)
        p_name = PIECE_CHARS[abs(moved_p)][0] if moved_p > 0 else "기물"
        cap_name = PIECE_CHARS[abs(cap_p)][1] if cap_p != EMPTY else ""

        # 플레이어 착수 실행 및 DB 저장
        if board.make_move((r1, c1), (r2, c2)):
            db.save_move_record(
                game_id=st.session_state.game_id,
                move_no=len(board.move_history),
                turn_side="CHO",
                piece_name=p_name,
                from_pos=(r1, c1),
                to_pos=(r2, c2),
                captured_name=cap_name,
                fen_str=json.dumps(board.board)
            )

            # AI 응수 및 DB 저장
            if board.turn == HAN:
                ai_mv = st.session_state.ai_player.select_best_move(board)
                if ai_mv:
                    ai_fr, ai_to = ai_mv
                    ai_p = board.get_piece(ai_fr[0], ai_fr[1])
                    ai_cap = board.get_piece(ai_to[0], ai_to[1])
                    ai_p_name = PIECE_CHARS[abs(ai_p)][1] if ai_p != EMPTY else "기물"
                    ai_cap_name = PIECE_CHARS[abs(ai_cap)][0] if ai_cap != EMPTY else ""

                    board.make_move(ai_fr, ai_to)
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
            st.rerun()
    except Exception as e:
        st.error(f"착수 오류: {e}")

# -------------------------------------------------------------
# 현재 보드 상태 및 규칙 맵 생성
# -------------------------------------------------------------
board_matrix = []
legal_moves_dict = {}

for r in range(10):
    row_list = []
    for c in range(9):
        p = board.board[r][c]
        row_list.append(p)
        if p != EMPTY:
            color = board.get_color(p)
            moves = board.get_legal_moves(r, c)
            legal_moves_dict[f"{r},{c}"] = moves
    board_matrix.append(row_list)

scores = board.calculate_scores()
game_over, winner = board.is_game_over()

# -------------------------------------------------------------
# 일체형 인터랙티브 HTML (즉각적인 화면 이동 + 백그라운드 DB 자동 저장)
# -------------------------------------------------------------
html_app = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
        user-select: none;
    }}
    body {{
        background: #111827;
        color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 4px;
    }}
    .status-banner {{
        background: #0f172a;
        border: 1px solid #1e293b;
        color: #f1f5f9;
        font-weight: 700;
        font-size: 15px;
        padding: 9px 24px;
        border-radius: 8px;
        margin-bottom: 10px;
        text-align: center;
        width: 100%;
        max-width: 500px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.4);
    }}
    .janggi-board-wrap {{
        position: relative;
        width: 100%;
        max-width: 500px;
        aspect-ratio: 9 / 10.35;
        background: #E5A358;
        border-radius: 14px;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.7), inset 0 0 0 2px #3c2411;
        overflow: hidden;
    }}
    canvas {{
        width: 100%;
        height: 100%;
        display: block;
        cursor: pointer;
    }}
    .footer-label {{
        margin-top: 6px;
        color: #64748b;
        font-size: 11px;
    }}
</style>
</head>
<body>

<div class="status-banner" id="statusBanner">
    {"🎉 초(楚) 승리!" if winner == 'CHO' else ("💀 한(漢) 승리!" if winner == 'HAN' else ("당신(초)의 차례입니다." if board.turn == CHO else "컴퓨터(한)가 응수했습니다."))}
</div>

<div class="janggi-board-wrap">
    <canvas id="janggiCanvas" width="540" height="621"></canvas>
</div>

<div class="footer-label">mimmi.co.kr • 한국 전통 장기 AI 대전</div>

<script>
    const canvas = document.getElementById('janggiCanvas');
    const ctx = canvas.getContext('2d');
    const statusBanner = document.getElementById('statusBanner');

    // 클라이언트 보드 상태
    let board = {json.dumps(board_matrix)};
    const legalMap = {json.dumps(legal_moves_dict)};
    let currentTurn = {board.turn}; // 1 = CHO, -1 = HAN
    let isOver = {"true" if game_over else "false"};

    const ROWS = 10;
    const COLS = 9;
    const PAD_X = 38;
    const PAD_Y = 38;
    const CELL_W = (540 - PAD_X * 2) / (COLS - 1);
    const CELL_H = (621 - PAD_Y * 2) / (ROWS - 1);

    let selectedPos = null;
    let validMoves = [];

    const PIECE_CONFIG = {{
        1: {{ char: '楚', hanChar: '漢', r: 31, choStroke: '#047857', hanStroke: '#C62828', score: 0 }},
        2: {{ char: '士', hanChar: '士', r: 21, choStroke: '#047857', hanStroke: '#C62828', score: 3 }},
        3: {{ char: '馬', hanChar: '馬', r: 23, choStroke: '#047857', hanStroke: '#C62828', score: 5 }},
        4: {{ char: '象', hanChar: '象', r: 23, choStroke: '#047857', hanStroke: '#C62828', score: 3 }},
        5: {{ char: '車', hanChar: '車', r: 24, choStroke: '#047857', hanStroke: '#C62828', score: 13 }},
        6: {{ char: '包', hanChar: '包', r: 23, choStroke: '#047857', hanStroke: '#C62828', score: 7 }},
        7: {{ char: '卒', hanChar: '兵', r: 20, choStroke: '#047857', hanStroke: '#C62828', score: 2 }}
    }};

    function getPos(r, c) {{
        return {{ x: PAD_X + c * CELL_W, y: PAD_Y + r * CELL_H }};
    }}

    function drawOctagon(ctx, x, y, r, fillColor, strokeColor, isSelected) {{
        // 외곽 팔각 테두리
        ctx.beginPath();
        for (let i = 0; i < 8; i++) {{
            const ang = (i * 45 + 22.5) * Math.PI / 180;
            const px = x + (r + 1.5) * Math.cos(ang);
            const py = y + (r + 1.5) * Math.sin(ang);
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        }}
        ctx.closePath();
        ctx.fillStyle = strokeColor;
        ctx.fill();

        // 내부 노란색 옥돌
        ctx.beginPath();
        for (let i = 0; i < 8; i++) {{
            const ang = (i * 45 + 22.5) * Math.PI / 180;
            const px = x + (r - 1.5) * Math.cos(ang);
            const py = y + (r - 1.5) * Math.sin(ang);
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        }}
        ctx.closePath();
        ctx.fillStyle = fillColor;
        ctx.fill();

        if (isSelected) {{
            ctx.strokeStyle = '#2563EB';
            ctx.lineWidth = 3.5;
            ctx.stroke();
        }}
    }}

    function render() {{
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // 1. 장기판 바탕색
        ctx.fillStyle = '#E5A358';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // 2. 격자선
        ctx.strokeStyle = '#26180a';
        ctx.lineWidth = 1.6;

        for (let r = 0; r < ROWS; r++) {{
            const y = PAD_Y + r * CELL_H;
            ctx.beginPath();
            ctx.moveTo(PAD_X, y);
            ctx.lineTo(canvas.width - PAD_X, y);
            ctx.stroke();
        }}
        for (let c = 0; c < COLS; c++) {{
            const x = PAD_X + c * CELL_W;
            ctx.beginPath();
            ctx.moveTo(x, PAD_Y);
            ctx.lineTo(x, canvas.height - PAD_Y);
            ctx.stroke();
        }}

        // 궁성 대각선
        function drawDiagonals(startR) {{
            const tl = getPos(startR, 3);
            const tr = getPos(startR, 5);
            const bl = getPos(startR + 2, 3);
            const br = getPos(startR + 2, 5);
            ctx.beginPath();
            ctx.moveTo(tl.x, tl.y);
            ctx.lineTo(br.x, br.y);
            ctx.moveTo(tr.x, tr.y);
            ctx.lineTo(bl.x, bl.y);
            ctx.stroke();
        }}
        drawDiagonals(0);
        drawDiagonals(7);

        // 3. 이동 가능한 경로 표시 (녹색 점 / 붉은 링)
        if (selectedPos && validMoves.length > 0) {{
            validMoves.forEach(m => {{
                const pt = getPos(m[0], m[1]);
                const destP = board[m[0]][m[1]];

                if (destP !== 0) {{
                    // 상대 기물 잡기 가능 위치
                    ctx.beginPath();
                    ctx.arc(pt.x, pt.y, 20, 0, Math.PI * 2);
                    ctx.strokeStyle = '#EF4444';
                    ctx.lineWidth = 3.5;
                    ctx.stroke();
                }} else {{
                    // 빈 자리 이동 가능 위치
                    ctx.beginPath();
                    ctx.arc(pt.x, pt.y, 8, 0, Math.PI * 2);
                    ctx.fillStyle = '#10B981';
                    ctx.fill();
                    ctx.strokeStyle = '#047857';
                    ctx.lineWidth = 1.5;
                    ctx.stroke();
                }}
            }});
        }}

        // 4. 기물 렌더링
        for (let r = 0; r < ROWS; r++) {{
            for (let c = 0; c < COLS; c++) {{
                const p = board[r][c];
                if (p === 0) continue;

                const pt = getPos(r, c);
                const isCho = p > 0;
                const pType = Math.abs(p);
                const cfg = PIECE_CONFIG[pType];
                const isSel = selectedPos && selectedPos.r === r && selectedPos.c === c;

                const stroke = isCho ? cfg.choStroke : cfg.hanStroke;
                const bodyColor = '#FACC15';

                drawOctagon(ctx, pt.x, pt.y, cfg.r, bodyColor, stroke, isSel);

                ctx.font = `900 ${{cfg.r * 1.05}}px '궁서', 'Gungsuh', 'Noto Serif KR', serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = stroke;
                const charStr = isCho ? cfg.char : cfg.hanChar;
                ctx.fillText(charStr, pt.x, pt.y + 1);
            }}
        }}
    }}

    // 로컬 AI 자동 응수 알고리즘 (지연 없이 즉각 실행)
    function runLocalAI() {{
        statusBanner.innerText = "컴퓨터(한)가 생각 중입니다...";
        setTimeout(() => {{
            // 한나라 기물의 모든 유효 수 수집
            let aiMoves = [];
            for (let r = 0; r < ROWS; r++) {{
                for (let c = 0; c < COLS; c++) {{
                    const p = board[r][c];
                    if (p < 0) {{
                        const key = `${{r}},${{c}}`;
                        const mvs = legalMap[key] || [];
                        mvs.forEach(to => {{
                            const targetP = board[to[0]][to[1]];
                            let scoreGain = 0;
                            if (targetP > 0) {{
                                scoreGain = PIECE_CONFIG[Math.abs(targetP)].score * 10;
                            }}
                            aiMoves.push({{ from: [r, c], to: to, score: scoreGain + Math.random() }});
                        }});
                    }}
                }}
            }}

            if (aiMoves.length > 0) {{
                // 가장 유리한 착수 선택
                aiMoves.sort((a, b) => b.score - a.score);
                const best = aiMoves[0];
                const aiP = board[best.from[0]][best.from[1]];
                board[best.to[0]][best.to[1]] = aiP;
                board[best.from[0]][best.from[1]] = 0;
                currentTurn = 1; // 초나라 차례로 복귀
                statusBanner.innerText = "당신(초)의 차례입니다.";
                render();
            }} else {{
                currentTurn = 1;
                statusBanner.innerText = "컴퓨터가 한수 쉬었습니다. 당신의 차례입니다.";
                render();
            }}
        }}, 400);
    }}

    // 마우스 클릭 이벤트: 기물 선택 & 즉각 이동
    canvas.addEventListener('click', function(e) {{
        if (isOver || currentTurn !== 1) return;

        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const clickX = (e.clientX - rect.left) * scaleX;
        const clickY = (e.clientY - rect.top) * scaleY;

        let targetR = -1;
        let targetC = -1;
        let minDist = 26;

        for (let r = 0; r < ROWS; r++) {{
            for (let c = 0; c < COLS; c++) {{
                const pt = getPos(r, c);
                const d = Math.hypot(pt.x - clickX, pt.y - clickY);
                if (d < minDist) {{
                    minDist = d;
                    targetR = r;
                    targetC = c;
                }}
            }}
        }}

        if (targetR === -1 || targetC === -1) return;

        // [동작 2] 이미 기물이 선택되어 있고, 클릭한 곳이 이동 경로인 경우 -> 즉시 이동!
        if (selectedPos) {{
            const canMove = validMoves.some(m => m[0] === targetR && m[1] === targetC);
            if (canMove) {{
                // 1. 화면상에서 기물 즉각 이동! (버벅임 제로)
                const movedPiece = board[selectedPos.r][selectedPos.c];
                board[targetR][targetC] = movedPiece;
                board[selectedPos.r][selectedPos.c] = 0;

                const fromR = selectedPos.r;
                const fromC = selectedPos.c;
                selectedPos = null;
                validMoves = [];
                currentTurn = -1; // 컴퓨터 턴
                render();

                // 2. 서버 DB 저장을 위해 백그라운드 호출 (화면 새로고침 없이 비동기 저장)
                fetch(`?save_move=${{fromR}},${{fromC}},${{targetR}},${{targetC}}&t=${{Date.now()}}`)
                    .catch(err => console.log('DB sync'));

                // 3. 상대 컴퓨터 AI 즉각 응수 실행
                runLocalAI();
                return;
            }}
        }}

        // [동작 1] 내 기물(초나라 p > 0) 클릭 시 이동 경로 보기
        const p = board[targetR][targetC];
        if (p > 0) {{
            selectedPos = {{ r: targetR, c: targetC }};
            const key = `${{targetR}},${{targetC}}`;
            validMoves = legalMap[key] || [];
            statusBanner.innerText = `기물 선택됨 (이동 가능 경로 ${{validMoves.length}}곳 표시)`;
        }} else {{
            selectedPos = null;
            validMoves = [];
            statusBanner.innerText = "당신(초)의 차례입니다.";
        }}

        render();
    }});

    render();
</script>
</body>
</html>
"""

# -------------------------------------------------------------
# 메인 렌더링 영역
# -------------------------------------------------------------
col_l, col_board, col_history = st.columns([1, 6, 3])

with col_board:
    components.html(html_app, height=720, scrolling=False)

with col_history:
    st.markdown("### 📜 대국 기보 (착수 자동 저장)")
    st.caption(f"대국 ID: `{st.session_state.game_id}` • SQLite 실시간 저장")

    s1, s2 = st.columns(2)
    with s1:
        st.metric("🔵 초 (나)", f"{scores['CHO']}점")
    with s2:
        st.metric("🔴 한 (AI)", f"{scores['HAN']}점")

    if st.button("🔄 새 대국 시작", use_container_width=True, type="primary"):
        st.session_state.game_id = f"GAME_{int(time.time())}"
        st.session_state.board = JanggiBoard()
        st.rerun()

    # DB에 저장된 착수 기록 실시간 조회
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
        st.info("💡 **이동 방법**: 장기알을 클릭하면 이동 가능한 위치가 **녹색 원(🟢)**으로 표시됩니다. 녹색 원을 마우스로 클릭하면 **말이 즉시 이동**하고 DB에 저장됩니다.")

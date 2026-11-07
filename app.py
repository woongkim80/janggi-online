import streamlit as st
import base64
import json
import time
import os

from janggi_engine import JanggiBoard, CHO, HAN, PIECE_CHARS, EMPTY
from janggi_ai import JanggiAI
import database as db

# SQLite 데이터베이스 초기화
db.init_db()

st.set_page_config(
    page_title="장기 AI 대전",
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
# 제공해주신 원본 장기판 이미지(user_board.jpg) Base64 로드
# -------------------------------------------------------------
IMAGE_PATH = os.path.join(os.path.dirname(__file__), "static", "user_board.jpg")
with open(IMAGE_PATH, "rb") as f:
    BOARD_IMG_BASE64 = base64.b64encode(f.read()).decode("utf-8")

# -------------------------------------------------------------
# 현재 보드 상태 및 합법적 이동 경로 계산
# -------------------------------------------------------------
board_matrix = []
legal_moves_dict = {}

for r in range(10):
    row_list = []
    for c in range(9):
        p = board.board[r][c]
        row_list.append(p)
        if p != EMPTY and board.get_color(p) == board.turn:
            moves = board.get_legal_moves(r, c)
            legal_moves_dict[f"{r},{c}"] = moves
    board_matrix.append(row_list)

scores = board.calculate_scores()
game_over, winner = board.is_game_over()

# -------------------------------------------------------------
# 제공해주신 원본 이미지를 배경으로 한 인터랙티브 장기판 HTML
# -------------------------------------------------------------
html_content = f"""
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
        background: #0f172a;
        color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 10px;
    }}
    /* 상단 배너 */
    .top-status-bar {{
        background: #111e38;
        border: 1px solid #1e293b;
        color: #e2e8f0;
        font-weight: 700;
        font-size: 15px;
        padding: 10px 24px;
        border-radius: 8px;
        margin-bottom: 12px;
        text-align: center;
        width: 100%;
        max-width: 490px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
    }}
    /* 제공해주신 원본 이미지가 정확히 들어가는 컨테이너 */
    .board-container {{
        position: relative;
        width: 100%;
        max-width: 480px;
        aspect-ratio: 468 / 525;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.6);
        border-radius: 12px;
        overflow: hidden;
    }}
    canvas {{
        width: 100%;
        height: 100%;
        display: block;
        cursor: pointer;
    }}
    .footer-label {{
        margin-top: 8px;
        color: #64748b;
        font-size: 11px;
    }}
</style>
</head>
<body>

<div class="top-status-bar" id="statusBar">
    {"🎉 초(楚) 승리!" if winner == 'CHO' else ("💀 한(漢) 승리!" if winner == 'HAN' else "당신(초)의 차례입니다.")}
</div>

<div class="board-container">
    <canvas id="janggiCanvas" width="468" height="525"></canvas>
</div>

<div class="footer-label">제공해주신 공식 장기판 원본 이미지 기반 AI 대전</div>

<script>
    const canvas = document.getElementById('janggiCanvas');
    const ctx = canvas.getContext('2d');
    const statusBar = document.getElementById('statusBar');

    // 사용자 제공 원본 이미지 객체 생성
    const bgImage = new Image();
    bgImage.src = "data:image/jpeg;base64,{BOARD_IMG_BASE64}";

    let board = {json.dumps(board_matrix)};
    const legalMap = {json.dumps(legal_moves_dict)};
    let currentTurn = 1; // 1 = CHO, -1 = HAN
    let isGameOver = false;

    const ROWS = 10;
    const COLS = 9;

    // 제공된 이미지의 장기판 격자 교차점 오프셋 정확 매핑
    const PAD_LEFT = 35;
    const PAD_RIGHT = 35;
    const PAD_TOP = 80;
    const PAD_BOTTOM = 38;
    const CELL_W = (468 - PAD_LEFT - PAD_RIGHT) / (COLS - 1);
    const CELL_H = (525 - PAD_TOP - PAD_BOTTOM) / (ROWS - 1);

    let selectedPos = null;
    let validMoves = [];

    // 기물 한자 및 크기 설정
    const PIECE_INFO = {{
        1: {{ char: '楚', hanChar: '漢', r: 24, choColor: '#047857', hanColor: '#C62828' }}, // 궁
        2: {{ char: '士', hanChar: '士', r: 17, choColor: '#047857', hanColor: '#C62828' }}, // 사
        3: {{ char: '馬', hanChar: '馬', r: 18, choColor: '#047857', hanColor: '#C62828' }}, // 마
        4: {{ char: '象', hanChar: '象', r: 18, choColor: '#047857', hanColor: '#C62828' }}, // 상
        5: {{ char: '車', hanChar: '車', r: 19, choColor: '#047857', hanColor: '#C62828' }}, // 차
        6: {{ char: '包', hanChar: '包', r: 18, choColor: '#047857', hanColor: '#C62828' }}, // 포
        7: {{ char: '卒', hanChar: '兵', r: 16, choColor: '#047857', hanColor: '#C62828' }}  // 졸/병
    }};

    function getCoord(r, c) {{
        return {{
            x: PAD_LEFT + c * CELL_W,
            y: PAD_TOP + r * CELL_H
        }};
    }}

    // 팔각 옥돌 기물 그리기 (제공 이미지 스타일)
    function drawOctagon(ctx, x, y, r, fillColor, strokeColor, isSelected) {{
        ctx.beginPath();
        for (let i = 0; i < 8; i++) {{
            const ang = (i * 45 + 22.5) * Math.PI / 180;
            const px = x + (r + 1) * Math.cos(ang);
            const py = y + (r + 1) * Math.sin(ang);
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        }}
        ctx.closePath();
        ctx.fillStyle = strokeColor;
        ctx.fill();

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
            ctx.lineWidth = 3;
            ctx.stroke();
        }}
    }}

    function render() {{
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // 1. 제공해주신 원본 장기판 이미지 배경 렌더링!
        if (bgImage.complete) {{
            ctx.drawImage(bgImage, 0, 0, canvas.width, canvas.height);
        }} else {{
            ctx.fillStyle = '#E5A358';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
        }}

        // 2. 이동 가능한 경로 표시 (녹색 점 / 붉은 타겟 링)
        if (selectedPos && validMoves.length > 0) {{
            validMoves.forEach(m => {{
                const pt = getCoord(m[0], m[1]);
                const targetP = board[m[0]][m[1]];

                if (targetP !== 0) {{
                    // 상대 기물 잡기 가능 위치
                    ctx.beginPath();
                    ctx.arc(pt.x, pt.y, 16, 0, Math.PI * 2);
                    ctx.strokeStyle = '#EF4444';
                    ctx.lineWidth = 3.5;
                    ctx.stroke();
                }} else {{
                    // 빈 자리 이동 가능 위치
                    ctx.beginPath();
                    ctx.arc(pt.x, pt.y, 7, 0, Math.PI * 2);
                    ctx.fillStyle = '#10B981';
                    ctx.fill();
                    ctx.strokeStyle = '#047857';
                    ctx.lineWidth = 1.5;
                    ctx.stroke();
                }}
            }});
        }}

        // 3. 기물 렌더링 (초나라/한나라)
        for (let r = 0; r < ROWS; r++) {{
            for (let c = 0; c < COLS; c++) {{
                const p = board[r][c];
                if (p === 0) continue;

                const pt = getCoord(r, c);
                const isCho = p > 0;
                const pType = Math.abs(p);
                const info = PIECE_INFO[pType];
                const isSel = selectedPos && selectedPos.r === r && selectedPos.c === c;

                const strokeColor = isCho ? info.choColor : info.hanColor;
                const bodyColor = '#FACC15';

                drawOctagon(ctx, pt.x, pt.y, info.r, bodyColor, strokeColor, isSel);

                ctx.font = `900 ${{info.r * 1.05}}px '궁서', 'Gungsuh', 'Noto Serif KR', serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = strokeColor;
                const charStr = isCho ? info.char : info.hanChar;
                ctx.fillText(charStr, pt.x, pt.y + 1);
            }}
        }}
    }}

    bgImage.onload = () => render();

    // 로컬 AI 자동 응수
    function runAI() {{
        statusBar.innerText = "컴퓨터(한)가 생각 중입니다...";
        setTimeout(() => {{
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
                            if (targetP > 0) scoreGain = 100;
                            aiMoves.push({{ from: [r, c], to: to, score: scoreGain + Math.random() }});
                        }});
                    }}
                }}
            }}

            if (aiMoves.length > 0) {{
                aiMoves.sort((a, b) => b.score - a.score);
                const best = aiMoves[0];
                const aiP = board[best.from[0]][best.from[1]];
                board[best.to[0]][best.to[1]] = aiP;
                board[best.from[0]][best.from[1]] = 0;
                currentTurn = 1;
                statusBar.innerText = "당신(초)의 차례입니다.";
                render();
            }} else {{
                currentTurn = 1;
                statusBar.innerText = "컴퓨터가 한수 쉬었습니다. 당신의 차례입니다.";
                render();
            }}
        }}, 400);
    }}

    // 마우스 클릭 이벤트: 1) 기물 선택(경로보기)  2) 경로 클릭(즉각 이동)
    canvas.addEventListener('click', function(e) {{
        if (isGameOver || currentTurn !== 1) return;

        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const clickX = (e.clientX - rect.left) * scaleX;
        const clickY = (e.clientY - rect.top) * scaleY;

        let targetR = -1;
        let targetC = -1;
        let minDist = 22;

        for (let r = 0; r < ROWS; r++) {{
            for (let c = 0; c < COLS; c++) {{
                const pt = getCoord(r, c);
                const d = Math.hypot(pt.x - clickX, pt.y - clickY);
                if (d < minDist) {{
                    minDist = d;
                    targetR = r;
                    targetC = c;
                }}
            }}
        }}

        if (targetR === -1 || targetC === -1) return;

        // [동작 2] 이미 기물이 선택되어 있고, 클릭한 곳이 '이동 경로'인 경우 -> 즉시 이동!
        if (selectedPos) {{
            const canMove = validMoves.some(m => m[0] === targetR && m[1] === targetC);
            if (canMove) {{
                // 1. 화면 즉시 이동
                const movedP = board[selectedPos.r][selectedPos.c];
                board[targetR][targetC] = movedP;
                board[selectedPos.r][selectedPos.c] = 0;

                selectedPos = null;
                validMoves = [];
                currentTurn = -1;
                render();

                // 2. AI 자동 응수
                runAI();
                return;
            }}
        }}

        // [동작 1] 내 기물(초나라 p > 0) 클릭 시 이동 경로 보기
        const p = board[targetR][targetC];
        if (p > 0) {{
            selectedPos = {{ r: targetR, c: targetC }};
            const key = `${{targetR}},${{targetC}}`;
            validMoves = legalMap[key] || [];
            statusBar.innerText = `기물 선택됨 (이동 가능 경로 ${{validMoves.length}}곳 표시)`;
        }} else {{
            selectedPos = null;
            validMoves = [];
            statusBar.innerText = "당신(초)의 차례입니다.";
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
    import streamlit.components.v1 as components
    components.html(html_content, height=650, scrolling=False)

with col_history:
    st.markdown("### 📜 대국 기보 & 조작")
    st.caption(f"대국 ID: `{st.session_state.game_id}`")

    s1, s2 = st.columns(2)
    with s1:
        st.metric("🔵 초 (나)", f"{scores['CHO']}점")
    with s2:
        st.metric("🔴 한 (AI)", f"{scores['HAN']}점")

    if st.button("🔄 새 대국 시작", use_container_width=True, type="primary"):
        st.session_state.game_id = f"GAME_{int(time.time())}"
        st.session_state.board = JanggiBoard()
        st.rerun()

    st.info("💡 **이동 방법**: 내 장기알(초)을 클릭하면 이동 가능한 위치가 **녹색 원(🟢)**으로 표시됩니다. 녹색 원을 마우스로 클릭하면 **말이 즉시 찰칵 이동**하고 컴퓨터 AI가 응수합니다.")

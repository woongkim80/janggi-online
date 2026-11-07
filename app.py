import streamlit as st
import base64
import json
import time
import os
import streamlit.components.v1 as components

from janggi_engine import JanggiBoard, CHO, HAN, PIECE_CHARS, EMPTY, K_KING, K_GUARD, K_HORSE, K_ELEPHANT, K_CHARIOT, K_CANNON, K_SOLDIER
from janggi_ai import JanggiAI
import database as db

# SQLite 데이터베이스 초기화
db.init_db()

st.set_page_config(
    page_title="온라인 AI 장기 대전",
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
# 현재 보드 상태 및 전체 기물(초/한) 합법적 이동 경로 계산
# -------------------------------------------------------------
board_matrix = []
all_legal_moves_dict = {}

for r in range(10):
    row_list = []
    for c in range(9):
        p = board.board[r][c]
        row_list.append(p)
        if p != EMPTY:
            # 초와 한 모든 기물의 합법 이동 경로를 미리 계산하여 프론트엔드로 전달
            moves = board.get_legal_moves(r, c)
            all_legal_moves_dict[f"{r},{c}"] = moves
    board_matrix.append(row_list)

scores = board.calculate_scores()
game_over, winner = board.is_game_over()

# -------------------------------------------------------------
# 사용자 제공 이미지와 100% 동일한 고품질 Canvas 장기판 HTML
# (배경 이미지에 기물이 이미 인쇄되어 있어 겹쳐 보이던 문제를 해결하기 위해,
#  사용자 이미지의 정밀 색상/규격을 바탕으로 순수 무결점 Canvas 판 위에만 기물을 렌더링)
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
        font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", sans-serif;
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 10px 0;
    }}
    /* 상단 상태 배너 (제공 이미지 스타일: 네이비 배경, 둥근 테두리) */
    .top-status-bar {{
        background: #000010;
        border: 1px solid #1e293b;
        color: #f1f5f9;
        font-weight: 700;
        font-size: 16px;
        padding: 10px 24px;
        border-radius: 8px;
        margin-bottom: 12px;
        text-align: center;
        width: 100%;
        max-width: 480px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.4);
    }}
    .board-container {{
        position: relative;
        width: 100%;
        max-width: 480px;
        aspect-ratio: 800 / 884;
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
        font-size: 12px;
        font-weight: 500;
        letter-spacing: 0.5px;
    }}
</style>
</head>
<body>

<div class="top-status-bar" id="statusBar">
    {"🎉 초(楚) 승리!" if winner == 'CHO' else ("💀 한(漢) 승리!" if winner == 'HAN' else "당신(초)의 차례입니다.")}
</div>

<div class="board-container">
    <canvas id="janggiCanvas" width="800" height="884"></canvas>
</div>

<div class="footer-label">mimmi.co.kr</div>

<script>
    const canvas = document.getElementById('janggiCanvas');
    const ctx = canvas.getContext('2d');
    const statusBar = document.getElementById('statusBar');

    let board = {json.dumps(board_matrix)};
    let legalMap = {json.dumps(all_legal_moves_dict)};
    let currentTurn = 1; // 1 = CHO, -1 = HAN
    let isGameOver = false;

    // 기보 이력 (되돌리기용 스택)
    let moveHistory = [];

    const ROWS = 10;
    const COLS = 9;

    // 제공된 이미지 규격 정밀 추출 좌표계 (800 x 884 픽셀)
    const X_START = 85.5;
    const X_STEP = 78.375;
    const Y_START = 100.0;
    const Y_STEP = 80.0;

    let selectedPos = null;
    let validMoves = [];

    // 기물 한자 및 크기 설정 (제공 이미지 스타일: 팔각형 노란 바탕, 초=청록색, 한=적색)
    const PIECE_INFO = {{
        1: {{ char: '楚', hanChar: '漢', r: 35, fontScale: 38 }}, // 궁 (대형)
        2: {{ char: '士', hanChar: '士', r: 24, fontScale: 26 }}, // 사
        3: {{ char: '馬', hanChar: '馬', r: 26, fontScale: 28 }}, // 마
        4: {{ char: '象', hanChar: '象', r: 26, fontScale: 28 }}, // 상
        5: {{ char: '車', hanChar: '車', r: 27, fontScale: 29 }}, // 차
        6: {{ char: '包', hanChar: '包', r: 26, fontScale: 28 }}, // 포
        7: {{ char: '卒', hanChar: '兵', r: 23, fontScale: 25 }}  // 졸/병
    }};

    function getCoord(r, c) {{
        return {{
            x: X_START + c * X_STEP,
            y: Y_START + r * Y_STEP
        }};
    }}

    // 1. 순수 원본 색상 장기판 배경 및 선 그리기 (겹침 현상 원천 제거)
    function drawBoardBackground() {{
        // 전체 캔버스 배경 (다크 네이비)
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // 원목 장기판 영역 (모서리 둥근 직사각형)
        const bx = 48;
        const by = 62;
        const bw = 704;
        const bh = 786;
        const cornerR = 14;

        ctx.fillStyle = '#DDA25E'; // 제공 이미지 원목 고유 색상 (#DDA25E)
        ctx.beginPath();
        ctx.roundRect(bx, by, bw, bh, cornerR);
        ctx.fill();

        // 장기판 외곽선
        ctx.strokeStyle = '#26180A';
        ctx.lineWidth = 2.5;
        ctx.stroke();

        // 격자선 색상
        ctx.strokeStyle = '#2E1A0C';
        ctx.lineWidth = 1.6;

        // 가로선 10개
        for (let r = 0; r < ROWS; r++) {{
            const y = Y_START + r * Y_STEP;
            ctx.beginPath();
            ctx.moveTo(X_START, y);
            ctx.lineTo(X_START + 8 * X_STEP, y);
            ctx.stroke();
        }}

        // 세로선 9개
        for (let c = 0; c < COLS; c++) {{
            const x = X_START + c * X_STEP;
            ctx.beginPath();
            ctx.moveTo(x, Y_START);
            ctx.lineTo(x, Y_START + 9 * Y_STEP);
            ctx.stroke();
        }}

        // 궁성 대각선 (한나라: 상단 row 0~2, col 3~5)
        const p1_top = getCoord(0, 3);
        const p1_bot = getCoord(2, 5);
        const p2_top = getCoord(0, 5);
        const p2_bot = getCoord(2, 3);

        ctx.beginPath();
        ctx.moveTo(p1_top.x, p1_top.y);
        ctx.lineTo(p1_bot.x, p1_bot.y);
        ctx.moveTo(p2_top.x, p2_top.y);
        ctx.lineTo(p2_bot.x, p2_bot.y);
        ctx.stroke();

        // 궁성 대각선 (초나라: 하단 row 7~9, col 3~5)
        const p3_top = getCoord(7, 3);
        const p3_bot = getCoord(9, 5);
        const p4_top = getCoord(7, 5);
        const p4_bot = getCoord(9, 3);

        ctx.beginPath();
        ctx.moveTo(p3_top.x, p3_top.y);
        ctx.lineTo(p3_bot.x, p3_bot.y);
        ctx.moveTo(p4_top.x, p4_top.y);
        ctx.lineTo(p4_bot.x, p4_bot.y);
        ctx.stroke();
    }}

    // 2. 제공 이미지와 100% 동일한 정통 팔각형 기물 렌더링
    function drawOctagonPiece(x, y, r, fillColor, strokeColor, isSelected) {{
        // 외곽 팔각 테두리
        ctx.beginPath();
        for (let i = 0; i < 8; i++) {{
            const ang = (i * 45 + 22.5) * Math.PI / 180;
            const px = x + (r + 1.2) * Math.cos(ang);
            const py = y + (r + 1.2) * Math.sin(ang);
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        }}
        ctx.closePath();
        ctx.fillStyle = strokeColor;
        ctx.fill();

        // 내부 밝은 황금빛 알 채우기 (#FACC15)
        ctx.beginPath();
        for (let i = 0; i < 8; i++) {{
            const ang = (i * 45 + 22.5) * Math.PI / 180;
            const px = x + (r - 2.0) * Math.cos(ang);
            const py = y + (r - 2.0) * Math.sin(ang);
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        }}
        ctx.closePath();
        ctx.fillStyle = fillColor;
        ctx.fill();

        // 선택되었을 때 파란 네온 링 표시
        if (isSelected) {{
            ctx.beginPath();
            ctx.arc(x, y, r + 7, 0, Math.PI * 2);
            ctx.strokeStyle = '#3B82F6';
            ctx.lineWidth = 3.5;
            ctx.stroke();
        }}
    }}

    // 기물 이동 가능 판정 함수 (프론트엔드 실시간 계산 지원)
    function getValidMoves(r, c) {{
        const key = `${{r}},${{c}}`;
        if (legalMap[key]) {{
            return legalMap[key];
        }}
        return [];
    }}

    // 전체 화면 렌더링
    function render() {{
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // 1. 단일 무결점 장기판 배경 렌더링
        drawBoardBackground();

        // 2. 선택된 기물의 이동 가능한 경로 표시 (녹색 점 / 붉은 타겟 링)
        if (selectedPos && validMoves.length > 0) {{
            validMoves.forEach(m => {{
                const pt = getCoord(m[0], m[1]);
                const targetP = board[m[0]][m[1]];

                if (targetP !== 0) {{
                    // 상대 기물 공격 가능 위치 (붉은 링)
                    ctx.beginPath();
                    ctx.arc(pt.x, pt.y, 22, 0, Math.PI * 2);
                    ctx.strokeStyle = '#DC2626';
                    ctx.lineWidth = 4;
                    ctx.stroke();
                }} else {{
                    // 빈 공간 이동 가능 위치 (선명한 녹색 원)
                    ctx.beginPath();
                    ctx.arc(pt.x, pt.y, 11, 0, Math.PI * 2);
                    ctx.fillStyle = '#10B981';
                    ctx.fill();
                    ctx.strokeStyle = '#047857';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }}
            }});
        }}

        // 3. 기물 렌더링
        for (let r = 0; r < ROWS; r++) {{
            for (let c = 0; c < COLS; c++) {{
                const p = board[r][c];
                if (p === 0) continue;

                const pt = getCoord(r, c);
                const isCho = p > 0;
                const pType = Math.abs(p);
                const info = PIECE_INFO[pType] || PIECE_INFO[7];
                const isSel = selectedPos && selectedPos.r === r && selectedPos.c === c;

                const strokeColor = isCho ? '#047857' : '#C62828'; // 초: 짙은 청록, 한: 붉은색
                const bodyColor = '#FACC15'; // 노란 옥돌

                drawOctagonPiece(pt.x, pt.y, info.r, bodyColor, strokeColor, isSel);

                // 궁서체 한자
                ctx.font = `900 ${{info.fontScale}}px '궁서', 'Gungsuh', 'Batang', serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = strokeColor;
                const charStr = isCho ? info.char : info.hanChar;
                ctx.fillText(charStr, pt.x, pt.y + 2);
            }}
        }}
    }}

    // 로컬 AI 자동 응수
    function runAI() {{
        statusBar.innerText = "컴퓨터(한)가 응수 중입니다...";
        setTimeout(() => {{
            let aiMoves = [];

            // 한나라 기물(p < 0)의 가능한 모든 수 탐색
            for (let r = 0; r < ROWS; r++) {{
                for (let c = 0; c < COLS; c++) {{
                    const p = board[r][c];
                    if (p < 0) {{
                        const mvs = getValidMoves(r, c);
                        mvs.forEach(to => {{
                            const targetP = board[to[0]][to[1]];
                            let scoreGain = 0;
                            if (targetP > 0) {{
                                // 상대 기물 잡기 가중치
                                const targetType = Math.abs(targetP);
                                scoreGain = (targetType === 1) ? 1000 : (targetType === 5 ? 130 : targetType * 15);
                            }}
                            aiMoves.push({{
                                from: [r, c],
                                to: to,
                                score: scoreGain + Math.random() * 5
                            }});
                        }});
                    }}
                }}
            }}

            if (aiMoves.length > 0) {{
                aiMoves.sort((a, b) => b.score - a.score);
                const best = aiMoves[0];

                const aiP = board[best.from[0]][best.from[1]];
                const capturedP = board[best.to[0]][best.to[1]];

                // 기보 스택 기록
                moveHistory.push({{
                    from: best.from,
                    to: best.to,
                    piece: aiP,
                    captured: capturedP,
                    turn: -1
                }});

                board[best.to[0]][best.to[1]] = aiP;
                board[best.from[0]][best.from[1]] = 0;
                currentTurn = 1;
                statusBar.innerText = "당신(초)의 차례입니다.";
                render();
            }} else {{
                currentTurn = 1;
                statusBar.innerText = "컴퓨터가 한수 쉬었습니다. 당신(초)의 차례입니다.";
                render();
            }}
        }}, 450);
    }}

    // 되돌리기 함수 (외부 버튼 연동 지원)
    window.undoMove = function() {{
        if (moveHistory.length === 0) return;
        // AI 수 되돌리기
        if (moveHistory.length > 0 && moveHistory[moveHistory.length - 1].turn === -1) {{
            const lastAI = moveHistory.pop();
            board[lastAI.from[0]][lastAI.from[1]] = lastAI.piece;
            board[lastAI.to[0]][lastAI.to[1]] = lastAI.captured;
        }}
        // 내 수 되돌리기
        if (moveHistory.length > 0 && moveHistory[moveHistory.length - 1].turn === 1) {{
            const lastMy = moveHistory.pop();
            board[lastMy.from[0]][lastMy.from[1]] = lastMy.piece;
            board[lastMy.to[0]][lastMy.to[1]] = lastMy.captured;
        }}
        selectedPos = null;
        validMoves = [];
        currentTurn = 1;
        statusBar.innerText = "이전 수로 되돌렸습니다. 당신(초)의 차례입니다.";
        render();
    }};

    // 마우스 클릭 이벤트: 1) 기물 클릭 -> 경로 표시 / 2) 경로 클릭 -> 즉시 이동
    canvas.addEventListener('click', function(e) {{
        if (isGameOver || currentTurn !== 1) return;

        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const clickX = (e.clientX - rect.left) * scaleX;
        const clickY = (e.clientY - rect.top) * scaleY;

        let targetR = -1;
        let targetC = -1;
        let minDist = 34; // 클릭 감지 반경

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

        // [동작 2] 이미 기물이 선택되어 있고, 이동 경로(초록점/붉은링)를 클릭한 경우 -> 즉시 이동!
        if (selectedPos) {{
            const canMove = validMoves.some(m => m[0] === targetR && m[1] === targetC);
            if (canMove) {{
                const movedP = board[selectedPos.r][selectedPos.c];
                const capturedP = board[targetR][targetC];

                // 기보 스택 저장
                moveHistory.push({{
                    from: [selectedPos.r, selectedPos.c],
                    to: [targetR, targetC],
                    piece: movedP,
                    captured: capturedP,
                    turn: 1
                }});

                // 기물 이동 반영
                board[targetR][targetC] = movedP;
                board[selectedPos.r][selectedPos.c] = 0;

                selectedPos = null;
                validMoves = [];
                currentTurn = -1;
                render();

                // 컴퓨터 AI 자동 응수
                runAI();
                return;
            }}
        }}

        // [동작 1] 내 기물(초나라 p > 0) 클릭 시 이동 경로 보기
        const p = board[targetR][targetC];
        if (p > 0) {{
            selectedPos = {{ r: targetR, c: targetC }};
            validMoves = getValidMoves(targetR, targetC);
            statusBar.innerText = `기물 선택됨 (이동 가능 경로 ${{validMoves.length}}곳 표시)`;
        }} else {{
            selectedPos = null;
            validMoves = [];
            statusBar.innerText = "당신(초)의 차례입니다.";
        }}

        render();
    }});

    // 최초 렌더링
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
    components.html(html_content, height=720, scrolling=False)

with col_history:
    st.markdown("### 📜 대국 관리 및 점수")
    st.caption(f"대국 ID: `{st.session_state.game_id}`")

    s1, s2 = st.columns(2)
    with s1:
        st.metric("🔵 초 (나)", f"{scores['CHO']}점")
    with s2:
        st.metric("🔴 한 (AI)", f"{scores['HAN']}점")

    st.markdown("---")
    if st.button("🔄 새 대국 시작 (초기화)", use_container_width=True, type="primary"):
        st.session_state.game_id = f"GAME_{int(time.time())}"
        st.session_state.board = JanggiBoard()
        st.rerun()

    st.info("💡 **이동 방법**: 내 장기알(초)을 클릭하면 이동 가능한 위치가 **녹색 원(🟢)**과 **붉은 타겟(⭕)**으로 표시됩니다. 원하는 곳을 클릭하면 **즉시 말이 이동하고 AI가 정상 응수**합니다.")

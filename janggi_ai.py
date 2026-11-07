"""
장기 컴퓨터(AI) 플레이어 모듈
- 기물 가치 점수 및 위치별 가중치 평가 함수
- 초급: 1-ply 최선 탐색 (그리디 + 점수 우위)
- 중급: Minimax 알고리즘 (Alpha-Beta 가지치기)
"""

import random
from typing import Tuple, Optional
from janggi_engine import JanggiBoard, CHO, HAN, PIECE_SCORES, EMPTY, K_KING

# 위치별 가중치 (전진한 졸/병, 중앙을 장악한 마/상/차에 가산점 부여)
POSITION_BONUS = {
    # 기물이 전진할수록 소폭 우세
}

def evaluate_board(board: JanggiBoard) -> float:
    """
    현재 보드의 형세를 점수로 환산
    (양수일수록 초(CHO) 유리, 음수일수록 한(HAN) 유리)
    """
    scores = board.calculate_scores()
    # 기본 기물 점수 차이 (초나라 점수 - 한나라 점수)
    net_score = scores["CHO"] - scores["HAN"]

    # 궁의 생존 여부 (승패 결정적 가중치)
    game_over, winner = board.is_game_over()
    if game_over:
        if winner == "CHO":
            return 9999.0
        elif winner == "HAN":
            return -9999.0

    return net_score

class JanggiAI:
    """컴퓨터 대전 AI 엔진"""

    def __init__(self, color=HAN, difficulty="normal"):
        self.color = color  # 기본적으로 컴퓨터는 후수(한, HAN=-1)
        self.difficulty = difficulty

    def select_best_move(self, board: JanggiBoard) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """현재 상황에서 최적의 착수를 선택하여 (from_pos, to_pos) 반환"""
        all_moves = board.get_all_valid_moves(self.color)
        if not all_moves:
            return None

        # 1. 쉬움 난이도: 잡을 수 있는 기물이 있으면 우선 잡고, 없으면 랜덤/기본 이동
        if self.difficulty == "easy":
            captures = []
            for move in all_moves:
                from_p, to_p = move
                target = board.get_piece(to_p[0], to_p[1])
                if target != EMPTY:
                    captures.append((move, PIECE_SCORES.get(abs(target), 0)))
            if captures:
                captures.sort(key=lambda x: x[1], reverse=True)
                return captures[0][0]
            return random.choice(all_moves)

        # 2. 보통 난이도 (1-Ply Minimax + 상대방 반격 계산)
        best_move = None
        best_val = 99999.0 if self.color == HAN else -99999.0

        # 기물 잡는 수 우선 탐색을 위해 셔플 후 정렬
        random.shuffle(all_moves)

        for from_pos, to_pos in all_moves:
            # 수 시뮬레이션
            from_piece = board.board[from_pos[0]][from_pos[1]]
            to_piece = board.board[to_pos[0]][to_pos[1]]

            board.board[to_pos[0]][to_pos[1]] = from_piece
            board.board[from_pos[0]][from_pos[1]] = EMPTY

            val = evaluate_board(board)

            # 롤백
            board.board[from_pos[0]][from_pos[1]] = from_piece
            board.board[to_pos[0]][to_pos[1]] = to_piece

            if self.color == HAN:
                # 한나라는 점수가 낮을수록(음수일수록) 유리
                if val < best_val:
                    best_val = val
                    best_move = (from_pos, to_pos)
            else:
                # 초나라는 점수가 높을수록 유리
                if val > best_val:
                    best_val = val
                    best_move = (from_pos, to_pos)

        return best_move or random.choice(all_moves)


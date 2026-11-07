"""
한국 전통 장기(Janggi) 코어 룰 엔진
- 9 x 10 보드 상태 관리
- 초(CHO, 선수/청색) vs 한(HAN, 후수/홍색)
- 기물: 궁(King/General), 사(Guard), 차(Chariot), 포(Cannon), 마(Horse), 상(Elephant), 졸/병(Soldier)
- 장기 고유 규칙 (마/상 멱 판정, 포 도약 및 포끼리 불가, 궁성 대각선 이동 등)
"""

from typing import List, Tuple, Optional, Dict, Set
import copy

# 기물 정의 상수
# 초(CHO): 양수 (KING=1, GUARD=2, HORSE=3, ELEPHANT=4, CHARIOT=5, CANNON=6, SOLDIER=7)
# 한(HAN): 음수 (-1, -2, -3, -4, -5, -6, -7)
EMPTY = 0
K_KING = 1
K_GUARD = 2
K_HORSE = 3
K_ELEPHANT = 4
K_CHARIOT = 5
K_CANNON = 6
K_SOLDIER = 7

CHO = 1
HAN = -1

# 기물 표시 문자
PIECE_CHARS = {
    K_KING: ("楚", "漢"),
    K_GUARD: ("士", "士"),
    K_HORSE: ("馬", "馬"),
    K_ELEPHANT: ("象", "象"),
    K_CHARIOT: ("車", "車"),
    K_CANNON: ("包", "包"),
    K_SOLDIER: ("卒", "兵")
}

# 기물 점수 기준 (한국장기협회 공식 기준)
PIECE_SCORES = {
    K_KING: 0,
    K_GUARD: 3.0,
    K_HORSE: 5.0,
    K_ELEPHANT: 3.0,
    K_CHARIOT: 13.0,
    K_CANNON: 7.0,
    K_SOLDIER: 2.0
}

# 궁성(Palace) 좌표 정의 (row, col)
# 한(HAN) 궁성: row 0~2, col 3~5
HAN_PALACE = {(r, c) for r in range(3) for c in range(3, 6)}
# 초(CHO) 궁성: row 7~9, col 3~5
CHO_PALACE = {(r, c) for r in range(7, 10) for c in range(3, 6)}

# 궁성 대각선 경로 정의: (r, c) -> 갈 수 있는 대각선 이웃들
PALACE_DIAGONALS = {
    # 한나라 궁성 대각선 (0,3) <-> (1,4) <-> (2,5) / (0,5) <-> (1,4) <-> (2,3)
    (0, 3): [(1, 4)],
    (0, 5): [(1, 4)],
    (2, 3): [(1, 4)],
    (2, 5): [(1, 4)],
    (1, 4): [(0, 3), (0, 5), (2, 3), (2, 5)],
    
    # 초나라 궁성 대각선 (7,3) <-> (8,4) <-> (9,5) / (7,5) <-> (8,4) <-> (9,3)
    (7, 3): [(8, 4)],
    (7, 5): [(8, 4)],
    (9, 3): [(8, 4)],
    (9, 5): [(8, 4)],
    (8, 4): [(7, 3), (7, 5), (9, 3), (9, 5)]
}


class JanggiBoard:
    """9x10 장기판 모델 및 기물 이동 규칙 엔진"""

    def __init__(self, cho_formation="MSMS", han_formation="MSMS"):
        """
        포진(배치): 'MSMS'(마상마상), 'SMSM'(상마상마), 'MSSM'(마상상마), 'SMMS'(상마마상)
        """
        self.rows = 10
        self.cols = 9
        self.board: List[List[int]] = [[EMPTY for _ in range(self.cols)] for _ in range(self.rows)]
        self.turn = CHO  # 초(선수)가 먼저 시작
        self.move_history = []
        self.cho_formation = cho_formation
        self.han_formation = han_formation
        self.setup_board(cho_formation, han_formation)

    def setup_board(self, cho_form="MSMS", han_form="MSMS"):
        """초기 기물 배치"""
        self.board = [[EMPTY for _ in range(self.cols)] for _ in range(self.rows)]

        # 1. 한(HAN) 진영 (상단 row 0 ~ 4)
        # 차
        self.board[0][0] = -K_CHARIOT
        self.board[0][8] = -K_CHARIOT
        # 궁 및 사
        self.board[1][4] = -K_KING
        self.board[0][3] = -K_GUARD
        self.board[0][5] = -K_GUARD
        # 포
        self.board[2][1] = -K_CANNON
        self.board[2][7] = -K_CANNON
        # 병(兵)
        for c in [0, 2, 4, 6, 8]:
            self.board[3][c] = -K_SOLDIER

        # 한나라 마/상 배치 (col 1, 2, 6, 7)
        h_pieces = self._get_formation_pieces(han_form, side=HAN)
        self.board[0][1], self.board[0][2], self.board[0][6], self.board[0][7] = h_pieces

        # 2. 초(CHO) 진영 (하단 row 5 ~ 9)
        # 차
        self.board[9][0] = K_CHARIOT
        self.board[9][8] = K_CHARIOT
        # 궁 및 사
        self.board[8][4] = K_KING
        self.board[9][3] = K_GUARD
        self.board[9][5] = K_GUARD
        # 포
        self.board[7][1] = K_CANNON
        self.board[7][7] = K_CANNON
        # 졸(卒)
        for c in [0, 2, 4, 6, 8]:
            self.board[6][c] = K_SOLDIER

        # 초나라 마/상 배치 (col 1, 2, 6, 7)
        c_pieces = self._get_formation_pieces(cho_form, side=CHO)
        self.board[9][1], self.board[9][2], self.board[9][6], self.board[9][7] = c_pieces

    def _get_formation_pieces(self, formation: str, side: int):
        """마/상 포진에 따른 기물 리스트 반환 (col 1, 2, 6, 7)"""
        m = K_HORSE * side
        s = K_ELEPHANT * side
        f = formation.upper()
        if f == "SMSM":
            return [s, m, s, m]
        elif f == "MSSM":
            return [m, s, s, m]
        elif f == "SMMS":
            return [s, m, m, s]
        else:  # 기본 MSMS (마상마상)
            return [m, s, m, s]

    def is_valid_coord(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols

    def get_piece(self, r: int, c: int) -> int:
        if not self.is_valid_coord(r, c):
            return EMPTY
        return self.board[r][c]

    def get_color(self, piece: int) -> int:
        if piece > 0:
            return CHO
        elif piece < 0:
            return HAN
        return 0

    def calculate_scores(self) -> Dict[str, float]:
        """한국장기협회 기준 양측 기물 점수 계산 (한나라 덤 1.5점 포함)"""
        cho_score = 0.0
        han_score = 1.5  # 후수 덤 1.5점

        for r in range(self.rows):
            for c in range(self.cols):
                p = self.board[r][c]
                if p == EMPTY:
                    continue
                p_type = abs(p)
                score = PIECE_SCORES.get(p_type, 0.0)
                if p > 0:
                    cho_score += score
                else:
                    han_score += score

        return {"CHO": cho_score, "HAN": han_score}

    def get_legal_moves(self, r: int, c: int) -> List[Tuple[int, int]]:
        """(r, c) 위치의 기물이 이동할 수 있는 모든 합법적인 좌표 리스트 반환"""
        piece = self.get_piece(r, c)
        if piece == EMPTY:
            return []

        p_type = abs(piece)
        color = self.get_color(piece)
        moves = []

        if p_type == K_SOLDIER:
            moves = self._get_soldier_moves(r, c, color)
        elif p_type == K_CHARIOT:
            moves = self._get_chariot_moves(r, c, color)
        elif p_type == K_CANNON:
            moves = self._get_cannon_moves(r, c, color)
        elif p_type == K_HORSE:
            moves = self._get_horse_moves(r, c, color)
        elif p_type == K_ELEPHANT:
            moves = self._get_elephant_moves(r, c, color)
        elif p_type in (K_KING, K_GUARD):
            moves = self._get_king_guard_moves(r, c, color)

        return moves

    def _get_soldier_moves(self, r: int, c: int, color: int) -> List[Tuple[int, int]]:
        """졸/병 이동: 전진 1칸, 좌우 1칸 (후진 불가). 적 궁성 내에서는 대각선 전진 가능"""
        moves = []
        forward_r = r - 1 if color == CHO else r + 1

        # 1. 전진 및 좌우
        candidates = [(forward_r, c), (r, c - 1), (r, c + 1)]
        for nr, nc in candidates:
            if self.is_valid_coord(nr, nc):
                if self.get_color(self.board[nr][nc]) != color:
                    moves.append((nr, nc))

        # 2. 적 궁성 내 대각선 전진
        curr = (r, c)
        if curr in PALACE_DIAGONALS:
            for nr, nc in PALACE_DIAGONALS[curr]:
                # 전진 방향 대각선만 허용
                if (color == CHO and nr < r) or (color == HAN and nr > r):
                    if self.get_color(self.board[nr][nc]) != color:
                        moves.append((nr, nc))

        return moves

    def _get_chariot_moves(self, r: int, c: int, color: int) -> List[Tuple[int, int]]:
        """차(車) 이동: 상하좌우 직선 무제한. 궁성 대각선 통과 가능"""
        moves = []
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            while self.is_valid_coord(nr, nc):
                target = self.board[nr][nc]
                target_color = self.get_color(target)
                if target == EMPTY:
                    moves.append((nr, nc))
                else:
                    if target_color != color:
                        moves.append((nr, nc))
                    break
                nr += dr
                nc += dc

        # 궁성 내 대각선 직진
        palace = CHO_PALACE if (r, c) in CHO_PALACE else (HAN_PALACE if (r, c) in HAN_PALACE else None)
        if palace:
            self._add_palace_chariot_diagonals(r, c, color, moves)

        return moves

    def _add_palace_chariot_diagonals(self, r: int, c: int, color: int, moves: List[Tuple[int, int]]):
        """차가 궁성 모서리나 중심에 있을 때 대각선 이동"""
        diag_lines = [
            [(0, 3), (1, 4), (2, 5)],
            [(0, 5), (1, 4), (2, 3)],
            [(7, 3), (8, 4), (9, 5)],
            [(7, 5), (8, 4), (9, 3)],
        ]
        curr = (r, c)
        for line in diag_lines:
            if curr in line:
                idx = line.index(curr)
                # 앞쪽 방향
                for next_pt in line[idx + 1:]:
                    nr, nc = next_pt
                    tgt = self.board[nr][nc]
                    if tgt == EMPTY:
                        moves.append((nr, nc))
                    else:
                        if self.get_color(tgt) != color:
                            moves.append((nr, nc))
                        break
                # 뒤쪽 방향
                for prev_pt in reversed(line[:idx]):
                    nr, nc = prev_pt
                    tgt = self.board[nr][nc]
                    if tgt == EMPTY:
                        moves.append((nr, nc))
                    else:
                        if self.get_color(tgt) != color:
                            moves.append((nr, nc))
                        break

    def _get_cannon_moves(self, r: int, c: int, color: int) -> List[Tuple[int, int]]:
        """포(包) 이동: 다른 기물 1개를 반드시 넘어야 함. 포끼리는 넘거나 잡을 수 없음"""
        moves = []
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            jumped = False
            while self.is_valid_coord(nr, nc):
                target = self.board[nr][nc]
                if not jumped:
                    if target != EMPTY:
                        # 포는 다른 포를 넘을 수 없음
                        if abs(target) == K_CANNON:
                            break
                        jumped = True
                else:
                    # 다리를 넘은 후
                    if target == EMPTY:
                        moves.append((nr, nc))
                    else:
                        # 포는 포를 잡을 수 없고, 아군 기물도 잡을 수 없음
                        if abs(target) != K_CANNON and self.get_color(target) != color:
                            moves.append((nr, nc))
                        break
                nr += dr
                nc += dc

        # 궁성 대각선 포 넘기
        self._add_palace_cannon_diagonals(r, c, color, moves)
        return moves

    def _add_palace_cannon_diagonals(self, r: int, c: int, color: int, moves: List[Tuple[int, int]]):
        """궁성 대각선 포 도약 (모서리 -> 중심(기물있음) -> 반대편 모서리)"""
        diag_lines = [
            [(0, 3), (1, 4), (2, 5)],
            [(0, 5), (1, 4), (2, 3)],
            [(7, 3), (8, 4), (9, 5)],
            [(7, 5), (8, 4), (9, 3)],
        ]
        curr = (r, c)
        for line in diag_lines:
            if curr == line[0] or curr == line[2]:
                bridge = line[1]
                dest = line[2] if curr == line[0] else line[0]
                bridge_piece = self.board[bridge[0]][bridge[1]]
                dest_piece = self.board[dest[0]][dest[1]]
                if bridge_piece != EMPTY and abs(bridge_piece) != K_CANNON:
                    if dest_piece == EMPTY or (abs(dest_piece) != K_CANNON and self.get_color(dest_piece) != color):
                        moves.append(dest)

    def _get_horse_moves(self, r: int, c: int, color: int) -> List[Tuple[int, int]]:
        """마(馬) 이동: 전후좌우 1칸 직진 후 대각선 1칸. (직진 경로에 기물이 있으면 멱 막힘)"""
        moves = []
        # (직진 d1, 대각선 d2)
        horse_steps = [
            ((-1, 0), (-2, -1)), ((-1, 0), (-2, 1)),
            ((1, 0), (2, -1)),   ((1, 0), (2, 1)),
            ((0, -1), (-1, -2)), ((0, -1), (1, -2)),
            ((0, 1), (-1, 2)),   ((0, 1), (1, 2))
        ]
        for (br, bc), (tr, tc) in horse_steps:
            block_r, block_c = r + br, c + bc
            target_r, target_c = r + tr, c + tc
            if self.is_valid_coord(target_r, target_c):
                # 멱 확인 (직진 위치가 비어 있어야 함)
                if self.board[block_r][block_c] == EMPTY:
                    if self.get_color(self.board[target_r][target_c]) != color:
                        moves.append((target_r, target_c))
        return moves

    def _get_elephant_moves(self, r: int, c: int, color: int) -> List[Tuple[int, int]]:
        """상(象) 이동: 직진 1칸 + 대각선 2칸. (중간 2곳 중 하나라도 기물 있으면 멱 막힘)"""
        moves = []
        # (중간 멱1, 중간 멱2, 최종 목표)
        elephant_steps = [
            ((-1, 0), (-2, -1), (-3, -2)),
            ((-1, 0), (-2, 1), (-3, 2)),
            ((1, 0), (2, -1), (3, -2)),
            ((1, 0), (2, 1), (3, 2)),
            ((0, -1), (-1, -2), (-2, -3)),
            ((0, -1), (1, -2), (2, -3)),
            ((0, 1), (-1, 2), (-2, 3)),
            ((0, 1), (1, 2), (2, 3))
        ]
        for (b1_r, b1_c), (b2_r, b2_c), (tr, tc) in elephant_steps:
            p1_r, p1_c = r + b1_r, c + b1_c
            p2_r, p2_c = r + b2_r, c + b2_c
            tgt_r, tgt_c = r + tr, c + tc
            if self.is_valid_coord(tgt_r, tgt_c):
                # 2개의 멱이 모두 비어 있어야 함
                if self.board[p1_r][p1_c] == EMPTY and self.board[p2_r][p2_c] == EMPTY:
                    if self.get_color(self.board[tgt_r][tgt_c]) != color:
                        moves.append((tgt_r, tgt_c))
        return moves

    def _get_king_guard_moves(self, r: int, c: int, color: int) -> List[Tuple[int, int]]:
        """궁(King) & 사(Guard) 이동: 지정된 궁성 3x3 범위 안에서만 1칸씩 상하좌우 및 대각선 이동"""
        moves = []
        palace = CHO_PALACE if color == CHO else HAN_PALACE

        # 상하좌우 1칸
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if (nr, nc) in palace:
                if self.get_color(self.board[nr][nc]) != color:
                    moves.append((nr, nc))

        # 궁성 대각선 1칸
        curr = (r, c)
        if curr in PALACE_DIAGONALS:
            for nr, nc in PALACE_DIAGONALS[curr]:
                if (nr, nc) in palace:
                    if self.get_color(self.board[nr][nc]) != color:
                        moves.append((nr, nc))

        return moves

    def make_move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
        """기물 이동 실행 및 턴 전환 (성공 시 True)"""
        r1, c1 = from_pos
        r2, c2 = to_pos

        piece = self.get_piece(r1, c1)
        if piece == EMPTY:
            return False
        if self.get_color(piece) != self.turn:
            return False

        legal_moves = self.get_legal_moves(r1, c1)
        if to_pos not in legal_moves:
            return False

        captured = self.board[r2][c2]
        self.board[r2][c2] = piece
        self.board[r1][c1] = EMPTY

        self.move_history.append({
            "from": from_pos,
            "to": to_pos,
            "piece": piece,
            "captured": captured,
            "turn": self.turn
        })

        # 턴 전환
        self.turn = -self.turn
        return True

    def undo_move(self) -> bool:
        """직전 1수 무르기 (기물 위치 및 턴 복구)"""
        if not self.move_history:
            return False
        last = self.move_history.pop()
        if last.get("passed"):
            self.turn = last["turn"]
            return True

        fr, fc = last["from"]
        tr, tc = last["to"]
        piece = last["piece"]
        captured = last["captured"]

        self.board[fr][fc] = piece
        self.board[tr][tc] = captured
        self.turn = last["turn"]
        return True

    def pass_turn(self):
        """한수 쉼 (Pass)"""
        self.move_history.append({
            "from": None,
            "to": None,
            "piece": None,
            "captured": None,
            "turn": self.turn,
            "passed": True
        })
        self.turn = -self.turn

    def get_all_valid_moves(self, color: int) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """특정 진영이 둘 수 있는 모든 합법적인 수 리스트 [(from, to), ...]"""
        all_moves = []
        for r in range(self.rows):
            for c in range(self.cols):
                p = self.board[r][c]
                if self.get_color(p) == color:
                    moves = self.get_legal_moves(r, c)
                    for m in moves:
                        all_moves.append(((r, c), m))
        return all_moves

    def is_game_over(self) -> Tuple[bool, Optional[str]]:
        """궁이 잡혔는지 여부로 승패 판정"""
        has_cho_king = any(self.board[r][c] == K_KING for r in range(self.rows) for c in range(self.cols))
        has_han_king = any(self.board[r][c] == -K_KING for r in range(self.rows) for c in range(self.cols))

        if not has_cho_king:
            return True, "HAN"  # 한나라 승리
        if not has_han_king:
            return True, "CHO"  # 초나라 승리
        return False, None


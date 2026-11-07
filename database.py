"""
온라인 장기 데이터베이스 모듈
- SQLite 기반 단일 파일 영구 저장 (`janggi.db`)
- 대국 착수 기록(기보) 자동 저장 및 조회
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "janggi.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. 게임 착수 기록 테이블 (Move History 영구 보존)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS game_moves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id TEXT NOT NULL,
        move_number INTEGER NOT NULL,
        turn TEXT NOT NULL,          -- CHO / HAN
        piece_type TEXT NOT NULL,
        from_r INTEGER,
        from_c INTEGER,
        to_r INTEGER,
        to_c INTEGER,
        captured TEXT,
        board_fen TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # 2. 게임 대국 요약 테이블
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS games (
        game_id TEXT PRIMARY KEY,
        player_cho TEXT DEFAULT '플레이어 (초)',
        player_han TEXT DEFAULT '컴퓨터 AI (한)',
        winner TEXT,
        total_moves INTEGER DEFAULT 0,
        status TEXT DEFAULT 'PLAYING',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

def save_move_record(game_id: str, move_no: int, turn_side: str, piece_name: str,
                     from_pos: tuple, to_pos: tuple, captured_name: str = "", fen_str: str = ""):
    """착수 1건을 SQLite DB에 즉시 영구 저장"""
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    fr, fc = from_pos if from_pos else (-1, -1)
    tr, tc = to_pos if to_pos else (-1, -1)

    cursor.execute("""
        INSERT INTO game_moves (
            game_id, move_number, turn, piece_type, from_r, from_c, to_r, to_c, captured, board_fen, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (game_id, move_no, turn_side, piece_name, fr, fc, tr, tc, captured_name, fen_str, now_str))

    cursor.execute("""
        INSERT INTO games (game_id, total_moves, status, created_at, updated_at)
        VALUES (?, ?, 'PLAYING', ?, ?)
        ON CONFLICT(game_id) DO UPDATE SET total_moves = ?, updated_at = ?
    """, (game_id, move_no, now_str, now_str, move_no, now_str))

    conn.commit()
    conn.close()

def get_game_moves(game_id: str) -> List[Dict[str, Any]]:
    """해당 게임의 모든 착수 기록 반환"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM game_moves WHERE game_id = ? ORDER BY move_number ASC", (game_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

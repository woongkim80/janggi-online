"""
온라인 장기 데이터베이스 및 실시간 룸/관전/유저 관리 모듈
- SQLite 기반 단일 파일 영구 저장 (`janggi.db`)
- Google OAuth 유저 프로필 & ELO 레이팅 점수 관리
- 실시간 대전방 및 관전자 목록, 기보(Replay) 동기화
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

    # 1. 유저 테이블 (Google OAuth 연동 프로필)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        google_id TEXT UNIQUE,
        email TEXT NOT NULL,
        name TEXT NOT NULL,
        picture TEXT,
        rating INTEGER DEFAULT 1200,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        draws INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    # 2. 대전방 테이블 (실시간 대국 및 관전)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        room_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        cho_player_id TEXT,
        cho_player_name TEXT,
        han_player_id TEXT,
        han_player_name TEXT,
        status TEXT DEFAULT 'WAITING', -- WAITING, PLAYING, FINISHED
        winner TEXT,
        fen_state TEXT,
        move_history TEXT,
        spectators_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # 3. 실시간 관전 채팅 및 훈수 테이블
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS room_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id TEXT NOT NULL,
        sender_name TEXT NOT NULL,
        is_player INTEGER DEFAULT 0,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

# -------------------------------------------------------------
# 유저 프로필 관리
# -------------------------------------------------------------
def get_or_create_user(email: str, name: str, picture: str = "", google_id: str = "") -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if row:
        user = dict(row)
    else:
        cursor.execute("""
            INSERT INTO users (google_id, email, name, picture, rating, wins, losses, draws, created_at)
            VALUES (?, ?, ?, ?, 1200, 0, 0, 0, ?)
        """, (google_id or email, email, name, picture, now_str))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,))
        user = dict(cursor.fetchone())

    conn.close()
    return user

def update_user_record(email: str, is_win: bool, is_draw: bool = False):
    conn = get_connection()
    cursor = conn.cursor()
    if is_draw:
        cursor.execute("UPDATE users SET draws = draws + 1 WHERE email = ?", (email,))
    elif is_win:
        cursor.execute("UPDATE users SET wins = wins + 1, rating = rating + 16 WHERE email = ?", (email,))
    else:
        cursor.execute("UPDATE users SET losses = losses + 1, rating = MAX(800, rating - 14) WHERE email = ?", (email,))
    conn.commit()
    conn.close()

# -------------------------------------------------------------
# 대전방 및 실시간 동기화
# -------------------------------------------------------------
def list_active_rooms() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rooms WHERE status IN ('WAITING', 'PLAYING') ORDER BY updated_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def create_or_join_room(room_id: str, title: str, player_name: str, side: str = "CHO") -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT * FROM rooms WHERE room_id = ?", (room_id,))
    row = cursor.fetchone()

    if not row:
        cho_name = player_name if side == "CHO" else None
        han_name = player_name if side == "HAN" else None
        cursor.execute("""
            INSERT INTO rooms (room_id, title, cho_player_name, han_player_name, status, fen_state, move_history, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'WAITING', '', '[]', ?, ?)
        """, (room_id, title, cho_name, han_name, now_str, now_str))
        conn.commit()
    else:
        room = dict(row)
        if side == "CHO" and not room["cho_player_name"]:
            cursor.execute("UPDATE rooms SET cho_player_name = ?, updated_at = ? WHERE room_id = ?", (player_name, now_str, room_id))
        elif side == "HAN" and not room["han_player_name"]:
            cursor.execute("UPDATE rooms SET han_player_name = ?, status = 'PLAYING', updated_at = ? WHERE room_id = ?", (player_name, now_str, room_id))
        conn.commit()

    cursor.execute("SELECT * FROM rooms WHERE room_id = ?", (room_id,))
    res = dict(cursor.fetchone())
    conn.close()
    return res

def get_room(room_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rooms WHERE room_id = ?", (room_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def sync_room_state(room_id: str, board_matrix: List[List[int]], move_history: List[Any], status: str = "PLAYING", winner: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        UPDATE rooms 
        SET fen_state = ?, move_history = ?, status = ?, winner = ?, updated_at = ?
        WHERE room_id = ?
    """, (json.dumps(board_matrix), json.dumps(move_history), status, winner, now_str, room_id))
    conn.commit()
    conn.close()

def send_chat_message(room_id: str, sender_name: str, message: str, is_player: int = 0):
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO room_messages (room_id, sender_name, is_player, message, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (room_id, sender_name, is_player, message, now_str))
    conn.commit()
    conn.close()

def get_room_messages(room_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM room_messages WHERE room_id = ? ORDER BY id DESC LIMIT ?", (room_id, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return list(reversed(rows))

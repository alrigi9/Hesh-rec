# -*- coding: utf-8 -*-
import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "recmap.db"


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes SQLite schema for session persistence."""
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                meeting_date TEXT,
                duration_minutes REAL,
                duration TEXT,
                language TEXT DEFAULT 'auto',
                tags TEXT,
                user_id TEXT,
                session_data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions (created_at DESC);")
        conn.commit()


init_db()


def save_session_to_sqlite(session_dict: Dict[str, Any]) -> None:
    """Inserts or updates a meeting session record in SQLite."""
    session_id = session_dict.get("id") or f"session_{int(datetime.now().timestamp())}"
    title = session_dict.get("title") or "Untitled Meeting"
    meeting_date = session_dict.get("meeting_date") or datetime.now().strftime("%Y-%m-%d")
    duration_minutes = float(session_dict.get("duration_minutes") or 0.0)
    duration = str(session_dict.get("duration") or f"{duration_minutes:.0f}m")
    language = session_dict.get("language") or "auto"
    tags = json.dumps(session_dict.get("tags") or [])
    user_id = session_dict.get("user_id") or "guest"
    created_at = session_dict.get("created_at") or datetime.now().isoformat()
    session_data_json = json.dumps(session_dict)

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO sessions (id, title, meeting_date, duration_minutes, duration, language, tags, user_id, session_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                meeting_date = excluded.meeting_date,
                duration_minutes = excluded.duration_minutes,
                duration = excluded.duration,
                language = excluded.language,
                tags = excluded.tags,
                user_id = excluded.user_id,
                session_data = excluded.session_data,
                created_at = excluded.created_at
        """, (
            session_id,
            title,
            meeting_date,
            duration_minutes,
            duration,
            language,
            tags,
            user_id,
            session_data_json,
            created_at
        ))
        conn.commit()


def get_sessions_from_sqlite(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves session records from SQLite."""
    with get_db_connection() as conn:
        if user_id and user_id != "guest":
            cursor = conn.execute(
                "SELECT session_data FROM sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
                (user_id,)
            )
        else:
            cursor = conn.execute(
                "SELECT session_data FROM sessions ORDER BY created_at DESC LIMIT 50"
            )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            try:
                results.append(json.loads(r["session_data"]))
            except Exception:
                pass
        return results


def get_session_by_id_from_sqlite(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single session record by ID."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT session_data FROM sessions WHERE id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row["session_data"])
            except Exception:
                pass
        return None


def delete_session_from_sqlite(session_id: str) -> bool:
    """Deletes a session from SQLite."""
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return cursor.rowcount > 0

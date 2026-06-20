"""对话历史持久化 — SQLite 存储"""

import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Optional


class ConversationStore:
    """SQLite 对话存储（线程安全）"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

    def initialize(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                model_id TEXT NOT NULL DEFAULT 'deepseek',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                msg_type TEXT NOT NULL DEFAULT 'text',
                metadata TEXT DEFAULT '{}',
                created_at REAL NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.commit()
        return self

    @property
    def conn(self):
        if self._conn is None:
            self.initialize()
        return self._conn

    # ---- Conversations ----

    def create_conversation(self, title: str = "", model_id: str = "deepseek") -> dict:
        now = time.time()
        conv_id = str(uuid.uuid4())
        if not title:
            title = f"对话 {conv_id[:8]}"
        with self._lock:
            self.conn.execute(
                "INSERT INTO conversations (id, title, model_id, created_at, updated_at) VALUES (?,?,?,?,?)",
                (conv_id, title, model_id, now, now),
            )
            self.conn.commit()
        return {"id": conv_id, "title": title, "model_id": model_id, "created_at": now, "updated_at": now}

    def list_conversations(self, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, title, model_id, created_at, updated_at FROM conversations ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"id": r[0], "title": r[1], "model_id": r[2], "created_at": r[3], "updated_at": r[4]}
            for r in rows
        ]

    def get_conversation(self, conv_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT id, title, model_id, created_at, updated_at FROM conversations WHERE id=?",
            (conv_id,),
        ).fetchone()
        if not row:
            return None
        messages = self._get_messages(conv_id)
        return {
            "id": row[0], "title": row[1], "model_id": row[2],
            "created_at": row[3], "updated_at": row[4],
            "messages": messages,
        }

    def update_conversation(self, conv_id: str, title: str) -> bool:
        now = time.time()
        with self._lock:
            cur = self.conn.execute(
                "UPDATE conversations SET title=?, updated_at=? WHERE id=?",
                (title, now, conv_id),
            )
            self.conn.commit()
        return cur.rowcount > 0

    def delete_conversation(self, conv_id: str) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
            self.conn.commit()
        return cur.rowcount > 0

    # ---- Messages ----

    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        msg_type: str = "text",
        metadata: Optional[dict] = None,
    ) -> dict:
        now = time.time()
        msg_id = str(uuid.uuid4())
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        with self._lock:
            self.conn.execute(
                "INSERT INTO messages (id, conversation_id, role, content, msg_type, metadata, created_at) VALUES (?,?,?,?,?,?,?)",
                (msg_id, conv_id, role, content, msg_type, meta_json, now),
            )
            self.conn.execute(
                "UPDATE conversations SET updated_at=? WHERE id=?",
                (now, conv_id),
            )
            self.conn.commit()
        return {
            "id": msg_id, "conversation_id": conv_id, "role": role,
            "content": content, "msg_type": msg_type,
            "metadata": metadata or {}, "created_at": now,
        }

    def _get_messages(self, conv_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, role, content, msg_type, metadata, created_at FROM messages WHERE conversation_id=? ORDER BY created_at",
            (conv_id,),
        ).fetchall()
        return [
            {
                "id": r[0], "role": r[1], "content": r[2],
                "msg_type": r[3], "metadata": json.loads(r[4] or "{}"),
                "created_at": r[5],
            }
            for r in rows
        ]

    def get_stats(self) -> dict:
        conv_count = self.conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        msg_count = self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        return {"conversations": conv_count, "messages": msg_count}

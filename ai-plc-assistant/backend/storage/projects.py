"""项目管理存储 — SQLite"""

import os
import sqlite3
import time
import uuid
from typing import Optional


class ProjectStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def initialize(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL DEFAULT '',
                plc_type TEXT NOT NULL DEFAULT 'S7-1200',
                tia_version TEXT NOT NULL DEFAULT 'V18',
                language TEXT NOT NULL DEFAULT 'SCL',
                description TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                last_opened_at REAL NOT NULL
            )
        """)
        self._conn.commit()
        return self

    @property
    def conn(self):
        if self._conn is None:
            self.initialize()
        return self._conn

    def create(self, name: str, path: str = "", plc_type: str = "S7-1200",
               tia_version: str = "V18", language: str = "SCL", description: str = "") -> dict:
        now = time.time()
        pid = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO projects (id,name,path,plc_type,tia_version,language,description,created_at,updated_at,last_opened_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pid, name, path, plc_type, tia_version, language, description, now, now, now),
        )
        self.conn.commit()
        return self.get(pid)

    def list_all(self, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id,name,path,plc_type,tia_version,language,description,created_at,updated_at,last_opened_at FROM projects ORDER BY last_opened_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get(self, pid: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT id,name,path,plc_type,tia_version,language,description,created_at,updated_at,last_opened_at FROM projects WHERE id=?",
            (pid,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def update(self, pid: str, **kwargs) -> Optional[dict]:
        allowed = {"name", "path", "plc_type", "tia_version", "language", "description"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return self.get(pid)
        updates["updated_at"] = time.time()
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [pid]
        self.conn.execute(f"UPDATE projects SET {sets} WHERE id=?", vals)
        self.conn.commit()
        return self.get(pid)

    def touch(self, pid: str) -> bool:
        """更新 last_opened_at"""
        cur = self.conn.execute("UPDATE projects SET last_opened_at=? WHERE id=?", (time.time(), pid))
        self.conn.commit()
        return cur.rowcount > 0

    def delete(self, pid: str) -> bool:
        cur = self.conn.execute("DELETE FROM projects WHERE id=?", (pid,))
        self.conn.commit()
        return cur.rowcount > 0

    def _row_to_dict(self, row) -> dict:
        return {
            "id": row[0], "name": row[1], "path": row[2],
            "plc_type": row[3], "tia_version": row[4], "language": row[5],
            "description": row[6], "created_at": row[7],
            "updated_at": row[8], "last_opened_at": row[9],
        }

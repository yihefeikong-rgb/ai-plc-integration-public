"""PLC 工程搜索索引 — SQLite FTS5 全文索引与搜索"""

import os
import re
import sqlite3
import time
from pathlib import Path
from typing import List, Optional

from .scanner import scan_projects
from .parsers import parse_file


class SearchIndex:
    """基于 SQLite FTS5 的 PLC 工程全文搜索引擎"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def initialize(self):
        """初始化数据库和 FTS5 表"""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=OFF")

        # 主表
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                type TEXT NOT NULL,
                name TEXT DEFAULT '',
                block_name TEXT DEFAULT '',
                block_type TEXT DEFAULT '',
                content TEXT DEFAULT '',
                line INTEGER DEFAULT 0,
                indexed_at REAL DEFAULT 0
            )
        """)

        # FTS5 全文索引
        self._conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                name, block_name, content,
                content='entries',
                content_rowid='id',
                tokenize='unicode61 remove_diacritics 2'
            )
        """)

        self._conn.commit()
        return self

    @property
    def conn(self):
        if self._conn is None:
            self.initialize()
        return self._conn

    # ---- Indexing ----

    def index_projects(self, project_dirs: List[str], progress=None, *, allowed_root: str | None = None) -> dict:
        """扫描并索引多个项目目录

        Args:
            project_dirs: 要扫描的项目目录列表
            progress: 可选的回调函数 progress(current, total, message)

        Returns:
            {"files_scanned": int, "entries_indexed": int, "projects": int}
        """
        files = scan_projects(project_dirs, allowed_root=allowed_root)

        total = len(files)
        indexed = 0

        for i, file_info in enumerate(files):
            if progress:
                progress(i + 1, total, f"索引中: {Path(file_info['path']).name}")

            entries = parse_file(file_info["path"])
            for entry in entries:
                self._insert_entry(file_info["path"], entry)
                indexed += 1

        self.conn.commit()

        return {
            "files_scanned": total,
            "entries_indexed": indexed,
            "projects": len(project_dirs),
        }

    def index_file(self, file_path: str) -> int:
        """索引单个文件"""
        entries = parse_file(file_path)
        count = 0
        for entry in entries:
            self._insert_entry(file_path, entry)
            count += 1
        self.conn.commit()
        return count

    def _insert_entry(self, file_path: str, entry: dict):
        now = time.time()
        self.conn.execute(
            """INSERT INTO entries (file_path, type, name, block_name, block_type, content, line, indexed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                file_path,
                entry.get("type", "generic"),
                entry.get("name", ""),
                entry.get("block_name", ""),
                entry.get("block_type", ""),
                entry.get("content", ""),
                entry.get("line", 0),
                now,
            ),
        )
        # 同步更新 FTS 索引
        self.conn.execute(
            """INSERT INTO entries_fts (rowid, name, block_name, content)
               VALUES (last_insert_rowid(), ?, ?, ?)""",
            (entry.get("name", ""), entry.get("block_name", ""), entry.get("content", "")),
        )

    # ---- Search ----

    def search(self, query: str, limit: int = 20, offset: int = 0) -> dict:
        """全文搜索

        Args:
            query: 搜索关键词
            limit: 返回数量
            offset: 偏移量

        Returns:
            {"results": [...], "total": int, "query": str}
        """
        if not query.strip():
            return {"results": [], "total": 0, "query": query}

        # 含中文的查询走 LIKE 搜索（FTS5 unicode61 不处理 CJK 分词）
        if re.search(r'[\u4e00-\u9fff]', query):
            return self.search_simple(query, limit=limit)

        # 构建 FTS5 查询
        fts_query = self._build_fts_query(query)

        # 搜索
        cursor = self.conn.execute(
            """SELECT e.id, e.file_path, e.type, e.name, e.block_name, e.block_type,
                      e.content, e.line, e.indexed_at,
                      rank
               FROM entries_fts f
               JOIN entries e ON e.id = f.rowid
               WHERE entries_fts MATCH ?
               ORDER BY rank
               LIMIT ? OFFSET ?""",
            (fts_query, limit, offset),
        )

        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "file_path": row[1],
                "type": row[2],
                "name": row[3],
                "block_name": row[4],
                "block_type": row[5],
                "content": row[6],
                "line": row[7],
                "score": round(max(0, 100 - row[9] * 10), 1),
            })

        # 总数
        count_cursor = self.conn.execute(
            "SELECT COUNT(*) FROM entries_fts WHERE entries_fts MATCH ?",
            (fts_query,),
        )
        total = count_cursor.fetchone()[0]

        return {"results": results, "total": total, "query": query}

    def search_by_type(self, query: str, type_filter: str, limit: int = 20) -> dict:
        """按类型过滤搜索"""
        if not query.strip():
            return {"results": [], "total": 0, "query": query}

        fts_query = self._build_fts_query(query)
        cursor = self.conn.execute(
            """SELECT e.id, e.file_path, e.type, e.name, e.block_name, e.block_type,
                      e.content, e.line, e.indexed_at, rank
               FROM entries_fts f
               JOIN entries e ON e.id = f.rowid
               WHERE entries_fts MATCH ? AND e.type = ?
               ORDER BY rank
               LIMIT ?""",
            (fts_query, type_filter, limit),
        )

        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "file_path": row[1],
                "type": row[2],
                "name": row[3],
                "block_name": row[4],
                "block_type": row[5],
                "content": row[6],
                "line": row[7],
                "score": round(max(0, 100 - row[9] * 10), 1),
            })

        return {"results": results, "total": len(results), "query": query}

    def search_simple(self, query: str, limit: int = 20) -> dict:
        """LIKE 搜索后备 — 适用于中文等 FTS5 不支持的语言"""
        like = f"%{query}%"
        cursor = self.conn.execute(
            """SELECT id, file_path, type, name, block_name, block_type,
                      content, line, indexed_at
               FROM entries
               WHERE content LIKE ? OR name LIKE ? OR block_name LIKE ?
               LIMIT ?""",
            (like, like, like, limit),
        )
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "file_path": row[1],
                "type": row[2],
                "name": row[3],
                "block_name": row[4],
                "block_type": row[5],
                "content": row[6],
                "line": row[7],
                "score": 50.0,
            })
        return {"results": results, "total": len(results), "query": query}

    # ---- Management ----

    def get_stats(self) -> dict:
        """获取索引统计"""
        count = self.conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        type_stats = self.conn.execute(
            "SELECT type, COUNT(*) as cnt FROM entries GROUP BY type ORDER BY cnt DESC"
        ).fetchall()
        file_count = self.conn.execute(
            "SELECT COUNT(DISTINCT file_path) FROM entries"
        ).fetchone()[0]

        return {
            "total_entries": count,
            "total_files": file_count,
            "by_type": {row[0]: row[1] for row in type_stats},
        }

    def clear(self):
        """清空索引"""
        # entries_fts 使用 external-content 表；普通 DELETE 只会清空影子内容，
        # 不会移除倒排词项，导致 total 与实际结果不一致。
        self.conn.execute("INSERT INTO entries_fts(entries_fts) VALUES('delete-all')")
        self.conn.execute("DELETE FROM entries")
        self.conn.commit()

    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    # ---- Helpers ----

    def _build_fts_query(self, query: str) -> str:
        """构建 FTS5 查询字符串"""
        tokens = []
        for t in query.split():
            t = t.strip()
            if not t:
                continue
            if ':' in t or '*' in t:
                tokens.append(t)
            else:
                tokens.append(f'"{t}"')
        return " OR ".join(tokens) if tokens else query



"""SQLite 连接管理 — WAL 模式、foreign_keys 强制开启、自动迁移。"""

import sqlite3
from pathlib import Path

from .migrations import run_migrations


class DatabaseConnection:
    """SQLite 数据库连接管理器。"""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """创建连接，开启 WAL 模式和 foreign_keys，执行迁移。"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        run_migrations(conn)
        self._conn = conn
        return conn

    def close(self) -> None:
        """关闭连接。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        """获取当前连接（自动创建）。"""
        if self._conn is None:
            self.connect()
        return self._conn

    def __enter__(self) -> sqlite3.Connection:
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass  # 连接由调用方管理生命周期

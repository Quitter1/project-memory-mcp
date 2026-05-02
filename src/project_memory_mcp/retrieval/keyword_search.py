"""SQLite keyword search — 基于 LIKE/FTS 的保底搜索。"""

import sqlite3


class KeywordSearchService:
    """SQLite keyword search，永远可用，不依赖外部服务。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # TODO: 阶段 3 实现
    # search(project_id, query, **filters) -> list[SearchResult]

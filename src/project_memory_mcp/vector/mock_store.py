"""Mock 向量存储 — 使用 numpy 内存计算，MVP 阶段不依赖 Qdrant。"""

import numpy as np
from .base import VectorStore, SearchHit


class MockVectorStore(VectorStore):
    """基于 numpy 的内存向量存储。"""

    def __init__(self, dimension: int = 768):
        self.dimension = dimension
        self._store: dict[str, dict] = {}  # memory_id -> {vector, payload}
        self._available = True

    async def upsert(self, points: list[dict]) -> None:
        """批量插入。"""
        # TODO: 阶段 3 实现
        pass

    async def search(
        self,
        vector: list[float],
        project_id: str,
        scope_filter: list[str] | None = None,
        allowed_project_ids: list[str] | None = None,
        top_k: int = 10,
        score_threshold: float = 0.5,
    ) -> list[SearchHit]:
        """向量相似度搜索 — numpy 余弦相似度 + payload filter。"""
        # TODO: 阶段 3 实现
        return []

    async def delete(self, memory_ids: list[str]) -> None:
        """删除向量点。"""
        for mid in memory_ids:
            self._store.pop(mid, None)

    async def is_available(self) -> bool:
        """Mock store 总是可用。"""
        return self._available

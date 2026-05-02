"""Mock Embedder — 生成确定性伪向量，用于 MVP 阶段测试和跑通流程。"""

import hashlib
from .base import Embedder


class MockEmbedder(Embedder):
    """
    确定性伪向量生成器。
    使用 SHA256 哈希 + 归一化生成固定维度的伪向量。
    同一文本始终生成相同向量，方便测试验证。
    """

    def __init__(self, dimension: int = 768):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成伪向量。"""
        # TODO: 阶段 3 实现确定性伪向量算法
        return [[0.0] * self._dimension for _ in texts]

    async def embed_query(self, query: str) -> list[float]:
        """生成查询向量。"""
        # TODO: 阶段 3 实现
        return [0.0] * self._dimension

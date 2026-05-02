"""向量存储层 — 抽象接口 + Mock 实现 + Qdrant 预留。"""

from .base import VectorStore
from .mock_store import MockVectorStore

__all__ = ["VectorStore", "MockVectorStore"]

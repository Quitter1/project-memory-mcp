"""Embedder 抽象接口。"""

from abc import ABC, abstractmethod


class Embedder(ABC):
    """文本向量化抽象基类。"""

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量文本向量化。"""
        ...

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """查询文本向量化。"""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """向量维度。"""
        ...

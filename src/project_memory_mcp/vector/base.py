"""VectorStore 抽象接口。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchHit:
    """向量搜索结果项。"""
    memory_id: str
    score: float
    payload: dict


class VectorStore(ABC):
    """向量存储抽象基类。"""

    @abstractmethod
    async def upsert(self, points: list[dict]) -> None:
        """批量插入/更新向量点。"""
        ...

    @abstractmethod
    async def search(
        self,
        vector: list[float],
        project_id: str,
        scope_filter: list[str] | None = None,
        allowed_project_ids: list[str] | None = None,
        top_k: int = 10,
        score_threshold: float = 0.5,
    ) -> list[SearchHit]:
        """向量相似度搜索。"""
        ...

    @abstractmethod
    async def delete(self, memory_ids: list[str]) -> None:
        """删除向量点。"""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """检查向量存储是否可用。"""
        ...

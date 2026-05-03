"""Deduplicator — 知识去重：SHA256 哈希去重 + 语义相似检测（best-effort）。"""

from dataclasses import dataclass, field
from typing import Optional

from ..db.memory_repo import MemoryRepository
from ..utils.hashing import compute_content_hash


@dataclass
class DedupResult:
    """去重检测结果。"""
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    duplicate_title: str = ""
    similar_existing: list[dict] = field(default_factory=list)


class Deduplicator:
    """
    知识去重服务。

    两层检测：
    1. 哈希去重 — SHA256 精确匹配（同 project_id + 同 scope）
    2. 语义去重 — 向量相似度检测（best-effort，vector store 不可用时跳过）
    """

    SIMILARITY_THRESHOLD = 0.92

    # 仅活跃状态参与去重判定（rejected/deprecated/superseded 不视为重复）
    ACTIVE_STATUSES = {"candidate", "pending_review", "approved", "conflict"}

    def __init__(
        self,
        repo: MemoryRepository,
        vector_store=None,
        embedder=None,
    ):
        self.repo = repo
        self.vector_store = vector_store
        self.embedder = embedder

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def check(
        self,
        content: str,
        project_id: str,
        scope: str = "project",
    ) -> DedupResult:
        """
        执行完整去重检测（哈希 + 语义）。

        返回 DedupResult。
        """
        content_hash = compute_content_hash(content)

        # 1. 哈希去重（仅活跃状态）
        existing = self.repo.find_by_hash(
            content_hash, project_id, scope=scope, active_statuses=self.ACTIVE_STATUSES,
        )
        if existing is not None:
            return DedupResult(
                is_duplicate=True,
                duplicate_of=existing.id,
                duplicate_title=existing.title,
            )

        # 2. 语义去重（best-effort）
        similar = self.find_similar(content, project_id)

        return DedupResult(similar_existing=similar)

    def check_hash_only(
        self,
        content: str,
        project_id: str,
        scope: str = "project",
    ) -> DedupResult:
        """仅执行哈希去重（快速路径）。"""
        content_hash = compute_content_hash(content)
        existing = self.repo.find_by_hash(
            content_hash, project_id, scope=scope, active_statuses=self.ACTIVE_STATUSES,
        )
        if existing is not None:
            return DedupResult(
                is_duplicate=True,
                duplicate_of=existing.id,
                duplicate_title=existing.title,
            )
        return DedupResult()

    def find_similar(
        self,
        content: str,
        project_id: str,
    ) -> list[dict]:
        """
        语义相似搜索（best-effort）。

        vector store 不可用时返回空列表，不影响主流程。
        """
        if self.vector_store is None or self.embedder is None:
            return []

        try:
            embedding = self.embedder.embed(content)
            if embedding is None:
                return []

            results = self.vector_store.search(
                embedding,
                filter_conditions={"project_id": project_id},
                limit=5,
                score_threshold=self.SIMILARITY_THRESHOLD,
            )
            return [
                {
                    "id": r.get("id", ""),
                    "title": r.get("title", ""),
                    "similarity": round(r.get("score", 0), 4),
                }
                for r in results
            ]
        except Exception:
            return []

    @staticmethod
    def compute_hash(content: str) -> str:
        """计算内容 SHA256 哈希（便捷方法）。"""
        return compute_content_hash(content)

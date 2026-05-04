"""
VectorIndexer — 与 governance 联动，索引/删除/重建向量。
"""

import logging

logger = logging.getLogger("project_memory_mcp")


class VectorIndexer:
    """向量索引管理器。"""

    def __init__(self, memory_repo, embedder, vector_store):
        self.memory_repo = memory_repo
        self.embedder = embedder
        self.store = vector_store
        self._enabled = embedder is not None and vector_store is not None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def build_embedding_text(self, memory) -> str:
        """构造向量化文本，不含 source_evidence 原文。"""
        parts = [
            f"标题: {memory.title or ''}",
            f"类型: {memory.type or ''}",
            f"模块: {memory.module or ''}",
            f"标签: {', '.join(memory.tags) if memory.tags else ''}",
            f"内容: {(memory.content or '')[:4000]}",
        ]
        return "\n".join(parts)

    def index_memory(self, memory) -> bool:
        """为单条知识建立向量索引。"""
        if not self._enabled:
            return False
        if memory.status != "approved":
            logger.debug("skip_index: memory_id=%s status=%s", memory.id, memory.status)
            return False
        try:
            text = self.build_embedding_text(memory)
            vec = self.embedder.embed_text(text)
            self.store.upsert_memory(
                memory.id, vec,
                {
                    "memory_id": memory.id,
                    "project_id": memory.project_id,
                    "scope": memory.scope,
                    "status": memory.status,
                    "type": memory.type,
                    "module": memory.module,
                    "tags": memory.tags or [],
                    "allowed_projects": memory.allowed_projects or [],
                    "denied_projects": memory.denied_projects or [],
                    "risk_level": memory.risk_level or "low",
                    "updated_at": memory.updated_at or "",
                },
            )
            logger.info("vector_indexed: memory_id=%s", memory.id)
            return True
        except Exception as exc:
            logger.error("vector_index_failed: memory_id=%s exc_type=%s", memory.id, type(exc).__name__)
            return False

    def delete_memory(self, memory_id: str) -> bool:
        """删除向量。"""
        if not self._enabled:
            return False
        try:
            self.store.delete_memory(memory_id)
            return True
        except Exception as exc:
            logger.error("vector_delete_failed: memory_id=%s exc_type=%s", memory_id, type(exc).__name__)
            return False

    def reindex_all(self, project_id: str | None = None, dry_run: bool = False) -> dict:
        """重建所有 approved 知识的向量索引。"""
        if not self._enabled:
            return {"eligible": 0, "indexed": 0, "failed": 0, "skipped": 0}

        eligible = 0
        indexed = 0
        failed = 0

        if project_id:
            items = self.memory_repo.list_memories(project_id=project_id, limit=10000)
        else:
            items = self.memory_repo.list_memories(status_filter=["approved"], limit=10000)
            if not project_id:
                # filter approved manually when listing all
                pass

        approved_items = [m for m in items if m.status == "approved"]
        eligible = len(approved_items)

        if dry_run:
            logger.info("reindex_dry_run: eligible=%d", eligible)
            return {"eligible": eligible, "indexed": 0, "failed": 0, "skipped": 0}

        self.store.ensure_collection()
        for m in approved_items:
            if self.index_memory(m):
                indexed += 1
            else:
                failed += 1

        logger.info("reindex_complete: eligible=%d indexed=%d failed=%d", eligible, indexed, failed)
        return {"eligible": eligible, "indexed": indexed, "failed": failed, "skipped": 0}

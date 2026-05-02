"""去重 — 内容哈希完全匹配 + 语义相似度检测。"""


class Deduplicator:
    """知识去重器。"""

    def __init__(self, memory_repo, vector_store):
        self.memory_repo = memory_repo
        self.vector_store = vector_store

    # TODO: 阶段 4 实现
    # check_hash_duplicate(content_hash, project_id) -> MemoryItem | None
    # find_similar(content, project_id, threshold=0.92) -> list[SimilarItem]

"""KnowledgeSearchService — 统一搜索入口：keyword-first + 三级范围检索。"""

import sqlite3

from ..models.search_result import SearchResultSet
from .keyword_search import KeywordSearchService
from .ranker import ResultRanker


class KnowledgeSearchService:
    """
    统一搜索入口。

    策略：
    1. keyword search（SQLite LIKE，必须可用）
    2. vector search（best-effort，不可用时不影响主流程）
    3. 合并去重排序 → context_pack

    三级范围：
    1. project scope 知识（scope=project）
    2. shared scope 知识（scope=shared + allowed）
    3. global scope 知识（scope=global）
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        vector_store=None,
        embedder=None,
    ):
        self.keyword_search = KeywordSearchService(conn)
        self.ranker = ResultRanker()
        self.vector_store = vector_store
        self.embedder = embedder

    def search(
        self,
        project_id: str,
        query: str,
        modules: list[str] | None = None,
        types: list[str] | None = None,
        tags: list[str] | None = None,
        max_results: int = 10,
        min_confidence: float | None = None,
        include_shared: bool = True,
        include_global: bool = True,
        include_candidates: bool = False,
    ) -> SearchResultSet:
        """
        执行检索，返回 SearchResultSet（含 context_pack）。

        参数：
        - project_id: 当前项目
        - query: 搜索关键词
        - modules/types/tags: 可选过滤
        - max_results: 最大返回数
        - min_confidence: 最低置信度
        - include_shared/include_global: 是否包含共享/全局知识
        - include_candidates: 是否包含候选/待审核知识
        """
        # 1. keyword search（主搜索，内部不再截断）
        if query and query.strip():
            keyword_results = self.keyword_search.search(
                project_id=project_id,
                query=query,
                modules=modules,
                types=types,
                tags=tags,
                max_results=max_results * 3,  # 给三级范围留余量
                min_confidence=min_confidence,
                include_shared=include_shared,
                include_global=include_global,
                include_candidates=include_candidates,
            )
        else:
            keyword_results = self.keyword_search.search_empty(
                project_id=project_id,
                max_results=max_results * 3,
                modules=modules,
                types=types,
                tags=tags,
                min_confidence=min_confidence,
                include_shared=include_shared,
                include_global=include_global,
                include_candidates=include_candidates,
            )

        # 2. semantic search（best-effort）
        semantic_results = []
        fallback = False
        if self.vector_store is not None and self.embedder is not None:
            try:
                if await_check(self.vector_store) and query and query.strip():
                    # TODO: Phase 7 Qdrant 集成
                    pass
            except Exception:
                fallback = True

        # 3. 合并去重排序
        merged = self.ranker.merge(keyword_results, semantic_results)
        total_found = len(merged)

        # 4. 全局截断后构建 context_pack（复用 ResultRanker）
        limited = merged[:max_results]
        cp = self.ranker.build_context_pack(limited, query, project_id)

        return SearchResultSet(
            query=query,
            project_id=project_id,
            project_resolved=True,
            context_pack={
                "summary": cp.summary,
                "project_context": [
                    {
                        "id": i.id, "title": i.title, "content": i.content,
                        "type": i.type, "module": i.module, "scope": i.scope,
                        "confidence": i.confidence, "risk_level": i.risk_level,
                        "tags": i.tags, "source_evidence": i.source_evidence,
                        "match_type": i.match_type, "relevance_score": i.relevance_score,
                        "from_project": i.from_project,
                    }
                    for i in cp.project_context
                ],
                "shared_context": [
                    {
                        "id": i.id, "title": i.title, "content": i.content,
                        "type": i.type, "module": i.module, "scope": i.scope,
                        "confidence": i.confidence, "risk_level": i.risk_level,
                        "tags": i.tags, "source_evidence": i.source_evidence,
                        "match_type": i.match_type, "relevance_score": i.relevance_score,
                        "from_project": i.from_project,
                    }
                    for i in cp.shared_context
                ],
                "global_context": [
                    {
                        "id": i.id, "title": i.title, "content": i.content,
                        "type": i.type, "module": i.module, "scope": i.scope,
                        "confidence": i.confidence, "risk_level": i.risk_level,
                        "tags": i.tags, "source_evidence": i.source_evidence,
                        "match_type": i.match_type, "relevance_score": i.relevance_score,
                        "from_project": i.from_project,
                    }
                    for i in cp.global_context
                ],
            },
            total_found=total_found,
            total_returned=len(limited),
            search_method="keyword",
            fallback_activated=fallback,
        )


def await_check(store) -> bool:
    """同步检查 vector store 可用性（避免引入 asyncio 依赖）。"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return True  # 不能嵌套 await，假定可用
        return loop.run_until_complete(store.is_available())
    except RuntimeError:
        try:
            return asyncio.run(store.is_available())
        except Exception:
            return False
    except Exception:
        return False

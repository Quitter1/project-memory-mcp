"""
KnowledgeSearchService — 统一搜索入口：keyword-first + vector + hybrid merge。

Phase 10.3: 真实接入 Qdrant vector/hybrid search。
"""

import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from ..models.search_result import SearchResultSet, SearchResult
from .keyword_search import KeywordSearchService
from .ranker import ResultRanker

logger = logging.getLogger("project_memory_mcp")


class KnowledgeSearchService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        vector_store=None,
        embedder=None,
        search_config: dict | None = None,
    ):
        self.keyword_search = KeywordSearchService(conn)
        self.ranker = ResultRanker()
        self.vector_store = vector_store
        self.embedder = embedder
        self.conn = conn
        cfg = search_config or {}
        self.mode = cfg.get("mode", "keyword")
        self.keyword_weight = cfg.get("keyword_weight", 0.55)
        self.vector_weight = cfg.get("vector_weight", 0.45)
        self.vector_top_k = cfg.get("vector_top_k", 30)
        self.fallback_to_keyword = cfg.get("fallback_to_keyword", True)
        self.min_vector_score = cfg.get("min_vector_score", 0.001)
        self.vector_timeout_seconds = cfg.get("vector_timeout_seconds", 3)
        self.vector_cooldown_seconds = cfg.get("vector_cooldown_seconds", 60)
        self.max_search_seconds = cfg.get("max_search_seconds", 8)
        self._vector_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vector-search")
        self._vector_cooldown_until: float = 0.0

    def search(
        self, project_id, query,
        modules=None, types=None, tags=None,
        max_results=10, min_confidence=None,
        include_shared=True, include_global=True,
        include_candidates=False,
    ) -> SearchResultSet:
        import time
        t0 = time.monotonic()
        logger.info(
            "search_started project_id=%s mode=%s query_len=%d",
            project_id, self.mode, len(query) if query else 0,
        )

        # 1. keyword search (always)
        if query and query.strip():
            keyword_results = self.keyword_search.search(
                project_id=project_id, query=query,
                modules=modules, types=types, tags=tags,
                max_results=max_results * 3,
                min_confidence=min_confidence,
                include_shared=include_shared,
                include_global=include_global,
                include_candidates=include_candidates,
            )
        else:
            keyword_results = self.keyword_search.search_empty(
                project_id=project_id, max_results=max_results * 3,
                modules=modules, types=types, tags=tags,
                min_confidence=min_confidence,
                include_shared=include_shared,
                include_global=include_global,
                include_candidates=include_candidates,
            )

        # 2. vector search
        vector_hits = []
        fallback = False
        fallback_reason = ""
        search_method = "keyword"

        use_vector = (self.mode in ("vector", "hybrid")
                      and self.vector_store is not None
                      and self.embedder is not None
                      and query and query.strip())

        # cooldown: skip vector if recently timed out
        if use_vector and time.monotonic() < self._vector_cooldown_until:
            logger.info("vector_cooldown: skipping, cooldown_until=%.0f", self._vector_cooldown_until)
            use_vector = False
            fallback = True
            fallback_reason = "vector_cooldown"

        if use_vector:
            t_vec_start = time.monotonic()
            logger.info("vector_started request_id=... project=%s query_len=%d top_k=%d",
                        project_id, len(query) if query else 0, self.vector_top_k)

            # Run in worker thread for true timeout
            def _vector_worker():
                w_vec = []
                w_embed = self.embedder.embed_text(query)
                logger.info("vector_embed_done dim=%d", len(w_embed) if w_embed else 0)
                for scope_name, sf in [("project", True), ("shared", include_shared), ("global", include_global)]:
                    if not sf:
                        continue
                    w_hits = self.vector_store.search(w_embed, project_id, scope_filter=scope_name, top_k=self.vector_top_k)
                    logger.info("qdrant_query_done scope=%s hit_count=%d", scope_name, len(w_hits))
                    w_vec.extend(w_hits)
                return w_vec

            future = self._vector_executor.submit(_vector_worker)
            try:
                vector_hits = future.result(timeout=self.vector_timeout_seconds)
                logger.info("vector_worker_done hit_count=%d elapsed_ms=%.1f",
                            len(vector_hits), (time.monotonic() - t_vec_start) * 1000)
                if self.mode == "hybrid":
                    search_method = "hybrid"
                else:
                    search_method = "vector"
            except FutureTimeoutError:
                logger.warning("vector_search_timeout elapsed_ms=%.1f fallback_to_keyword",
                               (time.monotonic() - t_vec_start) * 1000)
                future.cancel()
                fallback = True
                fallback_reason = "vector_timeout"
                self._vector_cooldown_until = time.monotonic() + self.vector_cooldown_seconds
                vector_hits = []
            except Exception as exc:
                logger.warning("vector_search_failed exc_type=%s", type(exc).__name__)
                fallback = True
                fallback_reason = f"vector_error: {type(exc).__name__}"
                if not self.fallback_to_keyword:
                    vector_hits = []

        # 3. Convert vector hits to SearchResults
        t_kw = time.monotonic()
        logger.info("keyword_done keyword_count=%d elapsed_ms=%.1f", len(keyword_results), (t_kw - t0) * 1000)

        semantic_results = []
        if vector_hits:
            semantic_results = self._vector_hits_to_items(
                vector_hits, project_id, query,
                include_shared=include_shared, include_global=include_global,
                include_candidates=include_candidates,
                modules=modules, types=types, tags=tags,
                min_confidence=min_confidence,
            )
        t_vec = time.monotonic()
        logger.info("vector_done vector_count=%d elapsed_ms=%.1f", len(semantic_results), (t_vec - t_kw) * 1000)

        # 4. Hybrid merge
        keyword_count = len(keyword_results)
        vector_count = len(semantic_results)

        if search_method == "hybrid":
            merged = self._hybrid_merge(keyword_results, semantic_results)
            hybrid_count = len(merged)
        else:
            merged = self.ranker.merge(keyword_results, semantic_results)
            hybrid_count = max(keyword_count, vector_count)

        total_found = len(merged)
        limited = merged[:max_results]
        cp = self.ranker.build_context_pack(limited, query, project_id)

        logger.info(
            "search_done total_returned=%d total_found=%d elapsed_ms=%.1f fallback=%s method=%s",
            len(limited), total_found, (time.monotonic() - t0) * 1000,
            fallback, search_method,
        )

        return SearchResultSet(
            query=query, project_id=project_id, project_resolved=True,
            context_pack={
                "summary": cp.summary,
                "project_context": [self._item_dict(i) for i in cp.project_context],
                "shared_context": [self._item_dict(i) for i in cp.shared_context],
                "global_context": [self._item_dict(i) for i in cp.global_context],
            },
            total_found=total_found, total_returned=len(limited),
            search_method=search_method, fallback_activated=fallback,
            fallback_reason=fallback_reason,
            keyword_count=keyword_count, vector_count=vector_count, hybrid_count=hybrid_count,
        )

    def _vector_hits_to_items(self, hits, project_id, query,
                               include_shared=True, include_global=True,
                               include_candidates=False,
                               modules=None, types=None, tags=None,
                               min_confidence=None):
        """将 Qdrant hits 转为 SearchResult，回 SQLite 读取完整内容。

        应用与 keyword search 一致的权限和过滤条件。
        """
        from ..db.memory_repo import MemoryRepository
        repo = MemoryRepository(self.conn)
        items = []
        seen = set()

        # 模块/类型/标签快速查找集合
        module_set = set(m.lower() for m in modules) if modules else None
        type_set = set(t.lower() for t in types) if types else None
        tag_set = set(t.lower() for t in tags) if tags else None

        for hit in hits:
            mid = hit.get("id", "")
            if mid in seen:
                continue
            seen.add(mid)

            score = hit.get("score", 0.0)
            if score < self.min_vector_score:
                continue

            memory = repo.get_by_id(mid)
            if memory is None:
                continue

            # 状态过滤
            if not include_candidates and memory.status not in ("approved",):
                continue
            if include_candidates and memory.status in ("rejected", "deprecated", "superseded", "conflict"):
                continue
            if not include_candidates and memory.status != "approved":
                continue

            # scope 权限
            if memory.scope == "project" and memory.project_id != project_id:
                continue
            if memory.scope == "shared":
                if not include_shared:
                    continue
                if memory.allowed_projects and project_id not in memory.allowed_projects:
                    continue
                if memory.denied_projects and project_id in memory.denied_projects:
                    continue
            if memory.scope == "global":
                if not include_global:
                    continue

            # 模块/类型/标签/min_confidence 过滤
            if module_set and memory.module.lower() not in module_set:
                continue
            if type_set and memory.type.lower() not in type_set:
                continue
            if tag_set and not any(t.lower() in tag_set for t in (memory.tags or [])):
                continue
            if min_confidence is not None and memory.confidence < min_confidence:
                continue

            items.append(SearchResult(
                id=memory.id, title=memory.title, content=memory.content,
                type=memory.type, module=memory.module, scope=memory.scope,
                confidence=memory.confidence, risk_level=memory.risk_level,
                tags=memory.tags, source_evidence=memory.source_evidence,
                match_type="vector", relevance_score=score,
                from_project=memory.project_id,
            ))
        return items

    def _hybrid_merge(self, keyword_items, vector_items):
        """keyword + vector 合并排序。"""
        mid_map = {}
        for item in keyword_items:
            kw_norm = min(item.relevance_score / 60.0, 1.0) if item.relevance_score else 0.0
            mid_map[item.id] = {"item": item, "kw": kw_norm, "vec": 0.0}
        for item in vector_items:
            vs = max(min(item.relevance_score, 1.0), 0.0) if item.relevance_score else 0.0
            if item.id in mid_map:
                mid_map[item.id]["vec"] = vs
            else:
                mid_map[item.id] = {"item": item, "kw": 0.0, "vec": vs}

        results = []
        for mid, scores in mid_map.items():
            hybrid_score = self.keyword_weight * scores["kw"] + self.vector_weight * scores["vec"]
            item = scores["item"]
            item.relevance_score = hybrid_score
            if scores["kw"] > 0 and scores["vec"] > 0:
                item.match_type = "hybrid"
            results.append(item)

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results

    @staticmethod
    def _item_dict(i):
        return {
            "id": i.id, "title": i.title, "content": i.content,
            "type": i.type, "module": i.module, "scope": i.scope,
            "confidence": i.confidence, "risk_level": i.risk_level,
            "tags": i.tags, "source_evidence": i.source_evidence,
            "match_type": i.match_type, "relevance_score": i.relevance_score,
            "from_project": i.from_project,
        }

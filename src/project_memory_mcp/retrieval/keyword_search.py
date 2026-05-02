"""KeywordSearchService — SQLite LIKE 搜索，参数化查询，多字段打分。"""

import json
import re
import sqlite3

from ..models.search_result import SearchResult
from .filter_builder import FilterBuilder

_TOKENIZE_RE = re.compile(r"\s+")


class KeywordSearchService:
    """
    SQLite keyword search（保底可用，不依赖外部服务）。

    匹配字段 + 权重：
    - title: +10
    - tags: +8
    - module: +5
    - type: +3
    - content: +2
    - source_file: +2
    """

    FIELD_WEIGHTS = [
        ("title", 10),
        ("module", 5),
        ("type", 3),
        ("content", 2),
        ("source_file", 2),
    ]
    TAG_WEIGHT = 8

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

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
    ) -> list[SearchResult]:
        """执行 keyword search，返回按分数降序的 SearchResult 列表。"""
        keywords = self._tokenize(query)
        all_results: list[SearchResult] = []

        # 1. project scope
        all_results.extend(
            self._search_project_scope(
                project_id, keywords,
                include_candidates, modules, types, min_confidence, max_results,
            )
        )

        # 2. shared scope
        if include_shared:
            all_results.extend(
                self._search_shared_scope(
                    keywords, project_id, modules, types, min_confidence,
                )
            )

        # 3. global scope
        if include_global:
            all_results.extend(
                self._search_global_scope(keywords, modules, types, min_confidence)
            )

        # 标签过滤
        if tags:
            all_results = [r for r in all_results if any(t in r.tags for t in tags)]

        # 去重（同 id 取最高分）
        seen: dict[str, SearchResult] = {}
        for r in all_results:
            if r.id not in seen or r.relevance_score > seen[r.id].relevance_score:
                seen[r.id] = r

        deduped = list(seen.values())
        deduped.sort(key=lambda x: -x.relevance_score)
        # 不在此处截断，由 KnowledgeSearchService 统一按 max_results 截断
        return deduped

    def search_empty(
        self,
        project_id: str,
        max_results: int = 10,
        modules: list[str] | None = None,
        types: list[str] | None = None,
        tags: list[str] | None = None,
        min_confidence: float | None = None,
        include_shared: bool = True,
        include_global: bool = True,
        include_candidates: bool = False,
    ) -> list[SearchResult]:
        """空 query 按 updated_at 降序返回最近知识，遵守全部过滤规则。"""
        all_results: list[SearchResult] = []

        clause = FilterBuilder.build_project_filter(
            project_id, include_candidates, modules, types, min_confidence,
        )
        rows = self.conn.execute(
            f"SELECT * FROM memory_items WHERE {clause.sql} ORDER BY updated_at DESC LIMIT ?",
            clause.params + [max_results],
        ).fetchall()
        all_results.extend(self._rows_to_results(rows, project_id))

        if include_shared:
            clause = FilterBuilder.build_shared_filter(
                project_id, modules, types, min_confidence,
            )
            rows = self.conn.execute(
                f"SELECT * FROM memory_items WHERE {clause.sql} ORDER BY updated_at DESC LIMIT ?",
                clause.params + [max_results],
            ).fetchall()
            all_results.extend(self._rows_to_results(rows, project_id))

        if include_global:
            clause = FilterBuilder.build_global_filter(modules, types, min_confidence)
            rows = self.conn.execute(
                f"SELECT * FROM memory_items WHERE {clause.sql} ORDER BY updated_at DESC LIMIT ?",
                clause.params + [max_results],
            ).fetchall()
            all_results.extend(self._rows_to_results(rows, project_id))

        # 标签过滤
        if tags:
            all_results = [r for r in all_results if any(t in r.tags for t in tags)]

        return all_results

    # ------------------------------------------------------------------
    # 内部：按 scope 搜索
    # ------------------------------------------------------------------

    def _search_project_scope(
        self, project_id, keywords, include_candidates, modules, types, min_confidence, max_results,
    ) -> list[SearchResult]:
        clause = FilterBuilder.build_project_filter(
            project_id, include_candidates, modules, types, min_confidence,
        )
        return self._execute_search(clause, keywords, project_id, max_results)

    def _search_shared_scope(
        self, keywords, project_id, modules, types, min_confidence,
    ) -> list[SearchResult]:
        clause = FilterBuilder.build_shared_filter(
            project_id, modules, types, min_confidence,
        )
        return self._execute_search(clause, keywords, project_id, 20)

    def _search_global_scope(
        self, keywords, modules, types, min_confidence,
    ) -> list[SearchResult]:
        clause = FilterBuilder.build_global_filter(modules, types, min_confidence)
        return self._execute_search(clause, keywords, None, 20)

    def _execute_search(
        self,
        clause,
        keywords: list[str],
        project_id: str | None,
        limit: int,
    ) -> list[SearchResult]:
        """通用搜索执行：无关键词 → 排序返回；有关键词 → 打分排序。"""
        if not keywords:
            rows = self.conn.execute(
                f"SELECT * FROM memory_items WHERE {clause.sql} ORDER BY updated_at DESC LIMIT ?",
                clause.params + [limit],
            ).fetchall()
            return self._rows_to_results(rows, project_id)

        score_parts, score_params = self._build_score(keywords)
        where_conds, where_params = self._build_where(keywords)

        # 顺序：SELECT 中的 score_params → WHERE clause → OR where_conds → LIMIT
        params = score_params + clause.params + where_params + [limit * 2]
        sql = (
            f"SELECT *, ({' + '.join(score_parts)}) AS relevance_score "
            f"FROM memory_items "
            f"WHERE {clause.sql} AND ({' OR '.join(where_conds)}) "
            f"ORDER BY relevance_score DESC LIMIT ?"
        )

        rows = self.conn.execute(sql, params).fetchall()
        return self._rows_to_results(rows, project_id)

    # ------------------------------------------------------------------
    # 评分 + 命中条件构建
    # ------------------------------------------------------------------

    def _build_score(self, keywords: list[str]) -> tuple[list[str], list]:
        """构建 SELECT 中的 CASE 打分表达式。"""
        parts: list[str] = []
        params: list = []
        for field, weight in self.FIELD_WEIGHTS:
            for kw in keywords:
                parts.append(f"CASE WHEN {field} LIKE ? THEN {weight} ELSE 0 END")
                params.append(f"%{kw}%")
        for kw in keywords:
            parts.append(
                f"CASE WHEN id IN "
                f"(SELECT memory_id FROM memory_tags WHERE tag LIKE ?) "
                f"THEN {self.TAG_WEIGHT} ELSE 0 END"
            )
            params.append(f"%{kw}%")
        return parts, params

    def _build_where(self, keywords: list[str]) -> tuple[list[str], list]:
        """构建 WHERE 子句中的命中条件（至少一个字段命中）。"""
        conds: list[str] = []
        params: list = []
        for field, _ in self.FIELD_WEIGHTS:
            for kw in keywords:
                conds.append(f"{field} LIKE ?")
                params.append(f"%{kw}%")
        for kw in keywords:
            conds.append(
                f"id IN (SELECT memory_id FROM memory_tags WHERE tag LIKE ?)"
            )
            params.append(f"%{kw}%")
        return conds, params

    # ------------------------------------------------------------------
    # 转换
    # ------------------------------------------------------------------

    def _rows_to_results(
        self, rows: list[sqlite3.Row], project_id: str | None,
    ) -> list[SearchResult]:
        """sqlite3.Row → SearchResult 列表。"""
        results: list[SearchResult] = []
        for r in rows:
            tag_rows = self.conn.execute(
                "SELECT tag FROM memory_tags WHERE memory_id = ?", (r["id"],)
            ).fetchall()
            tag_list = [t["tag"] for t in tag_rows]

            scope_val = r["scope"] or "project"
            from_proj = r["project_id"]
            if scope_val == "project" and project_id:
                from_proj = project_id

            # 解析 source_evidence JSON
            evidence: dict = {}
            se_val = r["source_evidence"] if "source_evidence" in r.keys() else None
            if se_val and isinstance(se_val, str):
                try:
                    evidence = json.loads(se_val)
                except (json.JSONDecodeError, TypeError):
                    evidence = {}
            if "file" not in evidence and r["source_file"]:
                evidence["file"] = r["source_file"]
            if "line" not in evidence and r["source_line"] is not None:
                evidence["line"] = r["source_line"]

            results.append(SearchResult(
                id=r["id"],
                title=r["title"] or "",
                content=r["content"] or "",
                type=r["type"] or "",
                module=r["module"] or "",
                scope=scope_val,
                confidence=r["confidence"] if r["confidence"] is not None else 0.0,
                risk_level=r["risk_level"] or "low",
                tags=tag_list,
                source_evidence=evidence,
                match_type="keyword",
                relevance_score=(
                    float(r["relevance_score"])
                    if "relevance_score" in r.keys() and r["relevance_score"] is not None
                    else 0.0
                ),
                from_project=from_proj,
            ))
        return results

    @staticmethod
    def _tokenize(query: str) -> list[str]:
        """分词：按空白拆分。"""
        if not query or not query.strip():
            return []
        return [t for t in _TOKENIZE_RE.split(query.strip()) if t]

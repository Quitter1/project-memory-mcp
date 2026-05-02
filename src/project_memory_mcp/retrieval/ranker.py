"""ResultRanker — 去重、排序、context_pack 组装。"""

from ..models.search_result import SearchResult
from ..models.context_pack import ContextPack, ContextPackItem


class ResultRanker:
    """搜索结果排序器 + context_pack 构建器。"""

    def merge(
        self,
        keyword_results: list[SearchResult],
        semantic_results: list[SearchResult] | None = None,
    ) -> list[SearchResult]:
        """
        合并 keyword + semantic 结果，去重保留最高分，按分数降序。

        MVP 阶段 semantic_results 为 None 或空列表。
        """
        all_results = list(keyword_results)
        if semantic_results:
            all_results.extend(semantic_results)

        seen: dict[str, SearchResult] = {}
        for r in all_results:
            if r.id not in seen or r.relevance_score > seen[r.id].relevance_score:
                seen[r.id] = r

        merged = list(seen.values())
        merged.sort(key=lambda x: -x.relevance_score)
        return merged

    def build_context_pack(
        self,
        results: list[SearchResult],
        query: str,
        project_id: str,
    ) -> ContextPack:
        """
        将合并后的结果按 scope 分组，构建 ContextPack。

        分组：
        - project_context: scope=project
        - shared_context: scope=shared
        - global_context: scope=global
        """
        project_items: list[ContextPackItem] = []
        shared_items: list[ContextPackItem] = []
        global_items: list[ContextPackItem] = []

        for r in results:
            item = ContextPackItem(
                id=r.id,
                title=r.title,
                content=r.content,
                type=r.type,
                module=r.module,
                scope=r.scope,
                confidence=r.confidence,
                risk_level=r.risk_level,
                tags=r.tags,
                source_evidence=r.source_evidence,
                match_type=r.match_type,
                relevance_score=r.relevance_score,
                from_project=r.from_project or project_id,
            )
            if r.scope == "shared":
                shared_items.append(item)
            elif r.scope == "global":
                global_items.append(item)
            else:
                project_items.append(item)

        summary = (
            f"找到 {len(project_items)} 条项目知识、"
            f"{len(shared_items)} 条共享知识、"
            f"{len(global_items)} 条全局知识。"
        )

        return ContextPack(
            summary=summary,
            project_context=project_items,
            shared_context=shared_items,
            global_context=global_items,
        )

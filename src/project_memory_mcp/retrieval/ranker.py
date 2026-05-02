"""结果排序/融合 + context_pack 组装。"""

from ..models.context_pack import ContextPack


class ResultRanker:
    """搜索结果排序器 + context_pack 构建器。"""

    # TODO: 阶段 3 实现
    # merge(keyword_results, semantic_results) -> list[SearchResult]
    # build_context_pack(results, query, project_id) -> ContextPack

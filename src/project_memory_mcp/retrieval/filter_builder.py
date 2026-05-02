"""过滤条件构建 — scope、project_id、status、type、module、tags。"""


class FilterBuilder:
    """构建 SQL WHERE 子句和 Qdrant filter。"""

    # TODO: 阶段 3 实现
    # build_sql_where(project_id, **filters) -> tuple[str, list]
    # build_qdrant_filter(project_id, **filters) -> dict

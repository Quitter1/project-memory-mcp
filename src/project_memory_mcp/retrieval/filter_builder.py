"""FilterBuilder — 构建参数化 SQL WHERE 子句，按 project/shared/global 三级过滤。"""


class FilterClause:
    """参数化 SQL 片段：(where_sql, params_list)。"""

    def __init__(self, sql: str, params: list):
        self.sql = sql
        self.params = params


class FilterBuilder:
    """
    构建检索过滤条件。

    三级范围：
    - project: scope=project, project_id=current
    - shared: scope=shared, allowed_projects 包含 current
    - global: scope=global
    """

    # 默认排除的状态（除非 include_candidates=True 或显式传入）
    DEFAULT_EXCLUDE_STATUSES = {"rejected", "deprecated", "superseded", "conflict"}

    # include_candidates=True 时允许的额外状态
    CANDIDATE_STATUSES = {"candidate", "pending_review"}

    # 基础状态（始终允许，不受 include_candidates 影响）
    BASE_STATUSES = {"approved"}

    @classmethod
    def build_project_filter(
        cls,
        project_id: str,
        include_candidates: bool = False,
        modules: list[str] | None = None,
        types: list[str] | None = None,
        min_confidence: float | None = None,
    ) -> FilterClause:
        """
        scope=project + project_id=current。

        返回 (sql, params)。
        """
        conditions = ["scope = 'project'", "project_id = ?"]
        params: list = [project_id]

        # 状态过滤
        status_sql, status_params = cls._status_clause(include_candidates)
        conditions.append(status_sql)
        params.extend(status_params)

        # 可选过滤
        extra_sql, extra_params = cls._optional_filters(modules, types, None, min_confidence)
        conditions.append(extra_sql)
        params.extend(extra_params)

        where = " AND ".join(conditions)
        return FilterClause(where, params)

    @classmethod
    def build_shared_filter(
        cls,
        project_id: str,
        modules: list[str] | None = None,
        types: list[str] | None = None,
        min_confidence: float | None = None,
    ) -> FilterClause:
        """
        scope=shared + status=approved。

        allowed_projects 为空（全部允许）或包含当前 project_id。
        denied_projects 不包含当前 project_id。
        """
        conditions = [
            "scope = 'shared'",
            "status = 'approved'",
            # allowed: 空 JSON 数组 或 包含 project_id（instr 精确匹配，避免 LIKE 通配符）
            "(allowed_projects = '[]' OR instr(allowed_projects, ?) > 0)",
            # denied: 不包含 project_id
            "(denied_projects = '[]' OR instr(denied_projects, ?) = 0)",
        ]
        project_id_pattern = f'"{project_id}"'
        params: list = [project_id_pattern, project_id_pattern]

        extra_sql, extra_params = cls._optional_filters(modules, types, None, min_confidence)
        conditions.append(extra_sql)
        params.extend(extra_params)

        where = " AND ".join(conditions)
        return FilterClause(where, params)

    @classmethod
    def build_global_filter(
        cls,
        modules: list[str] | None = None,
        types: list[str] | None = None,
        min_confidence: float | None = None,
    ) -> FilterClause:
        """scope=global + status=approved。"""
        conditions = ["scope = 'global'", "status = 'approved'"]
        params: list = []

        extra_sql, extra_params = cls._optional_filters(modules, types, None, min_confidence)
        conditions.append(extra_sql)
        params.extend(extra_params)

        where = " AND ".join(conditions)
        return FilterClause(where, params)

    @classmethod
    def build_tag_filter(
        cls,
        tags: list[str],
    ) -> FilterClause:
        """
        标签过滤 — 通过 memory_tags 子查询。

        注意：此过滤在三级范围外单独叠加。
        """
        if not tags:
            return FilterClause("1=1", [])
        placeholders = ", ".join("?" for _ in tags)
        # 使用 memory_id IN (SELECT memory_id FROM memory_tags WHERE tag IN (...))
        sql = f"id IN (SELECT DISTINCT memory_id FROM memory_tags WHERE tag IN ({placeholders}))"
        return FilterClause(sql, list(tags))

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @classmethod
    def _status_clause(cls, include_candidates: bool) -> tuple[str, list]:
        """构建状态过滤 SQL 片段，返回 (sql, params)。"""
        allowed = set(cls.BASE_STATUSES)
        if include_candidates:
            allowed.update(cls.CANDIDATE_STATUSES)
        statuses = sorted(allowed)
        placeholders = ", ".join("?" for _ in statuses)
        return f"status IN ({placeholders})", statuses

    @classmethod
    def _optional_filters(
        cls,
        modules: list[str] | None,
        types: list[str] | None,
        tags: list[str] | None,
        min_confidence: float | None,
    ) -> tuple[str, list]:
        """构建可选过滤条件。返回 (sql, params)。"""
        parts: list[str] = []
        params: list = []

        if modules:
            placeholders = ", ".join("?" for _ in modules)
            parts.append(f"module IN ({placeholders})")
            params.extend(modules)

        if types:
            placeholders = ", ".join("?" for _ in types)
            parts.append(f"type IN ({placeholders})")
            params.extend(types)

        if min_confidence is not None:
            parts.append("confidence >= ?")
            params.append(min_confidence)

        if parts:
            return " AND ".join(parts), params
        return "1=1", []

"""LifecycleManager — 知识双状态机：status（治理）+ index_status（索引）。"""

from ..models.enums import KnowledgeStatus, IndexStatus


class InvalidTransitionError(Exception):
    """非法状态转换。"""
    pass


class LifecycleManager:
    """
    知识双状态生命周期管理。

    status（治理状态）转换规则：
    - candidate → pending_review | approved | rejected
    - pending_review → approved | rejected
    - approved → deprecated | superseded | conflict
    - conflict → approved | rejected（冲突解决）
    - rejected → candidate（可重新提交）
    - deprecated / superseded → 终态（不可逆）

    index_status（索引状态）转换规则：
    - not_indexed → indexed | index_failed
    - indexed → stale
    - stale → indexed | index_failed
    - index_failed → not_indexed（重试）
    """

    STATUS_TRANSITIONS: dict[str, set[str]] = {
        KnowledgeStatus.CANDIDATE: {
            KnowledgeStatus.PENDING_REVIEW,
            KnowledgeStatus.APPROVED,
            KnowledgeStatus.REJECTED,
        },
        KnowledgeStatus.PENDING_REVIEW: {
            KnowledgeStatus.APPROVED,
            KnowledgeStatus.REJECTED,
        },
        KnowledgeStatus.APPROVED: {
            KnowledgeStatus.DEPRECATED,
            KnowledgeStatus.SUPERSEDED,
            KnowledgeStatus.CONFLICT,
        },
        KnowledgeStatus.CONFLICT: {
            KnowledgeStatus.APPROVED,
            KnowledgeStatus.REJECTED,
        },
        KnowledgeStatus.REJECTED: {KnowledgeStatus.CANDIDATE},
        KnowledgeStatus.DEPRECATED: set(),
        KnowledgeStatus.SUPERSEDED: set(),
    }

    INDEX_TRANSITIONS: dict[str, set[str]] = {
        IndexStatus.NOT_INDEXED: {IndexStatus.INDEXED, IndexStatus.INDEX_FAILED},
        IndexStatus.INDEXED: {IndexStatus.STALE},
        IndexStatus.STALE: {IndexStatus.INDEXED, IndexStatus.INDEX_FAILED},
        IndexStatus.INDEX_FAILED: {IndexStatus.NOT_INDEXED},
    }

    SEARCHABLE_STATUSES = {KnowledgeStatus.APPROVED}
    DEPRECATABLE_STATUSES = {KnowledgeStatus.APPROVED}
    REVIEWABLE_STATUSES = {KnowledgeStatus.CANDIDATE, KnowledgeStatus.PENDING_REVIEW}
    TERMINAL_STATUSES = {KnowledgeStatus.DEPRECATED, KnowledgeStatus.SUPERSEDED}

    # ------------------------------------------------------------------
    # status 转换
    # ------------------------------------------------------------------

    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        """检查 status 转换是否合法。"""
        return to_status in cls.STATUS_TRANSITIONS.get(from_status, set())

    @classmethod
    def validate_transition(cls, from_status: str, to_status: str) -> None:
        """验证 status 转换合法性，非法时抛出 InvalidTransitionError。"""
        if not cls.can_transition(from_status, to_status):
            allowed = cls.STATUS_TRANSITIONS.get(from_status, set())
            raise InvalidTransitionError(
                f"非法的状态转换: {from_status} → {to_status}，"
                f"允许的目标状态: {sorted(allowed) if allowed else '(终态，不可转换)'}"
            )

    @classmethod
    def get_allowed_transitions(cls, from_status: str) -> set[str]:
        """获取当前状态允许的目标状态集合。"""
        return cls.STATUS_TRANSITIONS.get(from_status, set())

    # ------------------------------------------------------------------
    # index_status 转换
    # ------------------------------------------------------------------

    @classmethod
    def can_transition_index(cls, from_index: str, to_index: str) -> bool:
        """检查 index_status 转换是否合法。"""
        return to_index in cls.INDEX_TRANSITIONS.get(from_index, set())

    @classmethod
    def validate_transition_index(cls, from_index: str, to_index: str) -> None:
        """验证 index_status 转换合法性。"""
        if not cls.can_transition_index(from_index, to_index):
            allowed = cls.INDEX_TRANSITIONS.get(from_index, set())
            raise InvalidTransitionError(
                f"非法的索引状态转换: {from_index} → {to_index}，"
                f"允许的目标状态: {sorted(allowed) if allowed else '(终态)'}"
            )

    # ------------------------------------------------------------------
    # 查询 helpers
    # ------------------------------------------------------------------

    @classmethod
    def is_searchable(cls, status: str) -> bool:
        """该状态的知识是否可被检索。"""
        return status in cls.SEARCHABLE_STATUSES

    @classmethod
    def is_terminal(cls, status: str) -> bool:
        """是否为终态（不可再转换）。"""
        return status in cls.TERMINAL_STATUSES

    @classmethod
    def is_reviewable(cls, status: str) -> bool:
        """是否可被审核（approve / reject）。"""
        return status in cls.REVIEWABLE_STATUSES

    @classmethod
    def is_deprecatable(cls, status: str) -> bool:
        """是否可被废弃。"""
        return status in cls.DEPRECATABLE_STATUSES

    @classmethod
    def initial_status(cls) -> str:
        """新知识的初始治理状态。"""
        return KnowledgeStatus.CANDIDATE

    @classmethod
    def initial_index_status(cls) -> str:
        """新知识的初始索引状态。"""
        return IndexStatus.NOT_INDEXED

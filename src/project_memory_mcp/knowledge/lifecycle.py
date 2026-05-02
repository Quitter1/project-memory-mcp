"""知识生命周期管理 — 双状态机（status + index_status）转换。"""

from ..models.enums import KnowledgeStatus, IndexStatus


class LifecycleManager:
    """管理知识 governance status 和 index status 的合法转换。"""

    # 状态转换合法路由表
    VALID_TRANSITIONS: dict[str, set[str]] = {
        KnowledgeStatus.CANDIDATE: {KnowledgeStatus.PENDING_REVIEW, KnowledgeStatus.REJECTED},
        KnowledgeStatus.PENDING_REVIEW: {KnowledgeStatus.APPROVED, KnowledgeStatus.REJECTED, KnowledgeStatus.CANDIDATE},
        KnowledgeStatus.APPROVED: {KnowledgeStatus.DEPRECATED, KnowledgeStatus.SUPERSEDED, KnowledgeStatus.CONFLICT},
        KnowledgeStatus.REJECTED: {KnowledgeStatus.CANDIDATE},  # 可重新提交
        KnowledgeStatus.DEPRECATED: set(),   # 终态
        KnowledgeStatus.SUPERSEDED: set(),   # 终态
        KnowledgeStatus.CONFLICT: {KnowledgeStatus.APPROVED},  # 解决冲突后恢复
    }

    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        """检查状态转换是否合法。"""
        return to_status in cls.VALID_TRANSITIONS.get(from_status, set())

    @classmethod
    def validate_transition(cls, from_status: str, to_status: str) -> None:
        """验证转换合法性，不合法则抛出 ValueError。"""
        if not cls.can_transition(from_status, to_status):
            raise ValueError(f"非法状态转换: {from_status} → {to_status}")

"""审核器 — MVP 使用 rule-based reviewer，预留 LLM reviewer 扩展点。

LLM Reviewer 不能绕过 policy，只能作为规则审核的补充建议。
"""

from abc import ABC, abstractmethod


class ReviewerBase(ABC):
    """审核器抽象基类。"""

    @abstractmethod
    async def review(self, memory_item: dict, project_config: dict) -> dict:
        """审核一条知识。返回 {decision, reason, suggestions}。"""
        ...


class RuleBasedReviewer(ReviewerBase):
    """基于规则的审核器 — MVP 实现。"""

    def __init__(self, memory_policy: dict):
        self.memory_policy = memory_policy

    async def review(self, memory_item: dict, project_config: dict) -> dict:
        """纯规则审核，不做 LLM 调用。"""
        # TODO: 阶段 4 实现
        return {"decision": "pending_review", "reason": "rule-based reviewer not implemented", "suggestions": []}


# 预留 LLM Reviewer 接口
# class LLMReviewer(ReviewerBase):
#     """LLM 审核器 — 后续实现。不能绕过 policy。"""
#     pass

"""RuleBasedReviewer — MVP 规则审核器，8 条件多因素联合判定。"""

from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from ..config.schema import ProjectConfig, ReviewPolicyConfig
from ..models.enums import Scope, RiskLevel, SourceType


@dataclass
class ReviewDecision:
    """审核决策结果。"""
    auto_approved: bool = False
    reason: str = ""
    required_reviewers: list[str] = field(default_factory=list)


class ReviewerBase(ABC):
    """审核器抽象基类。"""

    @abstractmethod
    def review(self, item: dict, project: ProjectConfig) -> ReviewDecision:
        """审核一条知识。返回 ReviewDecision。"""
        ...


class RuleBasedReviewer(ReviewerBase):
    """
    基于规则的审核器 — MVP 实现。

    自动批准需同时满足 8 个条件：
    1. confidence >= project.auto_approve_threshold
    2. scope == "project"（shared/global 永不自动批准）
    3. risk_level in ("low", "medium")（high/critical 永不自动批准）
    4. source_type 可信：
       - source_type in ("user_confirmed", "code_verified", "sql_verified")，或
       - source_type == "ai_inferred" AND review_policy.allow_ai_auto_approve == True
    5. 安全校验通过（无敏感信息命中）— 调用方确保
    6. 无内容哈希冲突 — 调用方确保
    7. 无语义冲突 — 调用方确保
    8. type 不在 review_policy.forbidden_auto_types 中
    """

    # 可信来源（可自动批准的 source_type）
    TRUSTED_SOURCES = {
        SourceType.USER_CONFIRMED,
        SourceType.CODE_VERIFIED,
        SourceType.SQL_VERIFIED,
    }

    # 安全的风险等级（可自动批准）
    SAFE_RISK_LEVELS = {RiskLevel.LOW, RiskLevel.MEDIUM}

    def review(
        self,
        item: dict,
        project: ProjectConfig,
        validation_passed: bool = True,
        has_duplicate: bool = False,
        has_conflict: bool = False,
    ) -> ReviewDecision:
        """
        执行多因素审批判定。

        参数：
        - item: 知识条目字典，含 confidence, scope, risk_level, source_type, type
        - project: 项目配置
        - validation_passed: 安全校验是否通过
        - has_duplicate: 是否存在哈希冲突
        - has_conflict: 是否存在语义冲突
        """
        rp: ReviewPolicyConfig = project.review_policy
        kp = project.knowledge_policy
        confidence = float(item.get("confidence", 0.5))
        scope = item.get("scope", Scope.PROJECT)
        risk_level = item.get("risk_level", RiskLevel.LOW)
        source_type = item.get("source_type", SourceType.AI_INFERRED)
        knowledge_type = item.get("type", "other")

        # === 条件 1: confidence >= threshold ===
        threshold = kp.auto_approve_threshold
        if confidence < threshold:
            return ReviewDecision(
                auto_approved=False,
                reason=f"confidence ({confidence}) < auto_approve_threshold ({threshold})",
            )

        # === 条件 2: scope == project ===
        if scope != Scope.PROJECT:
            return ReviewDecision(
                auto_approved=False,
                reason=f"scope={scope}，shared/global 知识禁止自动批准",
            )

        # === 条件 3: risk_level in (low, medium) ===
        if risk_level not in self.SAFE_RISK_LEVELS:
            return ReviewDecision(
                auto_approved=False,
                reason=f"risk_level={risk_level}，high/critical 禁止自动批准",
            )

        # === 条件 4: source_type 可信 ===
        if source_type not in self.TRUSTED_SOURCES:
            if source_type == SourceType.AI_INFERRED:
                if not rp.allow_ai_auto_approve:
                    return ReviewDecision(
                        auto_approved=False,
                        reason="AI 来源 + 项目禁止 AI 自动批准",
                    )
            else:
                return ReviewDecision(
                    auto_approved=False,
                    reason=f"source_type={source_type} 不在可信来源列表中",
                )

        # === 条件 5: 安全校验通过 ===
        if not validation_passed:
            return ReviewDecision(
                auto_approved=False,
                reason="安全校验未通过",
            )

        # === 条件 6: 无哈希冲突 ===
        if has_duplicate:
            return ReviewDecision(
                auto_approved=False,
                reason="存在内容哈希冲突",
            )

        # === 条件 7: 无语义冲突 ===
        if has_conflict and rp.require_review_if_conflict:
            return ReviewDecision(
                auto_approved=False,
                reason="存在语义冲突 + require_review_if_conflict=True",
            )

        # === 条件 8: type 不在 forbidden_auto_types ===
        if knowledge_type in rp.forbidden_auto_types:
            return ReviewDecision(
                auto_approved=False,
                reason=f"type={knowledge_type} 在 forbidden_auto_types 列表中",
            )

        return ReviewDecision(
            auto_approved=True,
            reason="满足全部 8 项自动批准条件",
        )

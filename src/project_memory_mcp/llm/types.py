"""LLM Reviewer 类型定义。"""

from dataclasses import dataclass, field


@dataclass
class LLMReviewResult:
    decision: str = "pending_review"  # approve | pending_review | reject
    confidence: float = 0.5
    risk_level: str = "low"           # low | medium | high
    reasons: list[str] = field(default_factory=list)
    suggested_type: str = ""
    suggested_tags: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    error: str = ""

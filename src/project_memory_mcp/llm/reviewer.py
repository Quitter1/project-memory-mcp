"""LLM Reviewer — 对候选知识做二次评审，不绕过 validator/governance。"""

import json
import logging
from .config import LLMReviewerConfig
from .client import LLMClient, LLMClientNotConfigured, LLMClientError
from .prompts import build_system_prompt, build_user_prompt
from .types import LLMReviewResult

logger = logging.getLogger("project_memory_mcp")

VALID_DECISIONS = {"approve", "pending_review", "reject"}
VALID_RISK_LEVELS = {"low", "medium", "high"}


def _sanitize_strs(items: list, max_items: int = 5, max_len: int = 300) -> list[str]:
    return [str(x)[:max_len] for x in (items or []) if isinstance(x, str)][:max_items]


def _parse_llm_response(raw: str) -> LLMReviewResult:
    """解析 LLM 输出的 JSON，做完整校验。"""
    # 提取 JSON（可能嵌在 markdown 代码块中）
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:]) if len(lines) > 1 else text
        if text.endswith("```"):
            text = text[:-3]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return LLMReviewResult(error="json_parse_failed", issues=["LLM 输出无法解析为 JSON"])

    decision = str(data.get("decision", "pending_review"))
    if decision not in VALID_DECISIONS:
        decision = "pending_review"

    try:
        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
    except (ValueError, TypeError):
        confidence = 0.5

    risk_level = str(data.get("risk_level", "low"))
    if risk_level not in VALID_RISK_LEVELS:
        risk_level = "low"

    reasons = _sanitize_strs(data.get("reasons", []))
    issues = _sanitize_strs(data.get("issues", []))
    suggested_type = str(data.get("suggested_type", ""))[:50]
    suggested_tags = [
        str(t)[:50] for t in (data.get("suggested_tags") or [])
        if isinstance(t, str)
    ][:5]

    return LLMReviewResult(
        decision=decision, confidence=confidence, risk_level=risk_level,
        reasons=reasons, issues=issues,
        suggested_type=suggested_type, suggested_tags=suggested_tags,
    )


class LLMReviewer:
    def __init__(self, config: LLMReviewerConfig | None = None):
        self.config = config or LLMReviewerConfig()
        self.client = LLMClient(self.config) if self.config.is_configured() else None

    @property
    def enabled(self) -> bool:
        return self.config.enabled and self.client is not None

    def review(self, proposal: dict) -> LLMReviewResult:
        if not self.enabled or self.client is None:
            return LLMReviewResult(decision="pending_review", error="llm_disabled")

        try:
            system_prompt = build_system_prompt()
            user_prompt = build_user_prompt(proposal)
            logger.info("llm_review_started prompt_len=%d", len(user_prompt))

            raw = self.client.chat(system_prompt, user_prompt)
            result = _parse_llm_response(raw)

            logger.info(
                "llm_review_done decision=%s confidence=%.2f risk=%s reasons=%d issues=%d",
                result.decision, result.confidence, result.risk_level,
                len(result.reasons), len(result.issues),
            )
            return result

        except LLMClientNotConfigured:
            return LLMReviewResult(decision="pending_review", error="llm_not_configured")
        except LLMClientError as exc:
            logger.warning("llm_review_error exc_type=%s", type(exc).__name__)
            return LLMReviewResult(decision="pending_review", error=f"llm_error: {type(exc).__name__}")
        except Exception as exc:
            logger.error("llm_review_exception exc_type=%s", type(exc).__name__)
            return LLMReviewResult(decision="pending_review", error="llm_exception")

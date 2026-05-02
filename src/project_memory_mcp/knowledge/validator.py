"""内容安全校验 — blocked(不保存原文) + warning(risk_level=high) 两级检测。"""

import re


class ContentValidator:
    """内容安全校验器。"""

    def __init__(self, config: dict):
        self.blocked_rules = config.get("blocked_rules", [])
        self.warning_rules = config.get("warning_rules", [])

    def validate(self, content: str) -> dict:
        """
        两级检测流程：
        1. blocked 规则 → 命中则返回 blocked=True，不保存原文
        2. warning 规则 → 命中则 risk_level=high，强制 pending_review
        返回 {passed, blocked, risk_level, errors, warnings}
        """
        # TODO: 阶段 4 实现
        return {"passed": True, "blocked": False, "risk_level": "low", "errors": [], "warnings": []}

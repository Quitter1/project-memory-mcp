"""ContentValidator — 敏感信息检测，两级：blocked（不保存原文）+ warning（risk_level=high）。"""

import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """校验结果。"""
    passed: bool = True
    risk_level: str = "low"       # low|medium|high|critical
    blocked: bool = False
    blocked_reason: str = ""
    warnings: list[str] = field(default_factory=list)


class ContentValidator:
    """
    敏感信息检测器。

    两级检测：
    1. blocked — 命中直接拒绝，不保存原文（私钥、AWS AKIA、明文密码、JDBC URL）
    2. warning — 命中则 risk_level=high，强制 pending_review
    """

    PRIVATE_KEY_RE = re.compile(
        r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|ENCRYPTED) PRIVATE KEY-----",
    )

    AWS_AKIA_RE = re.compile(r"AKIA[0-9A-Z]{16}")

    PLAINTEXT_PASSWORD_RE = re.compile(
        r"""password\s*[:=]\s*['"](?!\s*\$\{)[^'"]{6,}['"]""",
        re.IGNORECASE,
    )

    JDBC_PASSWORD_RE = re.compile(
        r"jdbc:[a-z]+://[^\s]*password=[^&\s]+",
        re.IGNORECASE,
    )

    API_KEY_ASSIGN_RE = re.compile(
        r"""(?:api[_-]?key|apikey|secret[_-]?key)\s*[:=]\s*['"]?[\w\-]{20,}['"]?""",
        re.IGNORECASE,
    )

    TOKEN_ASSIGN_RE = re.compile(
        r"""(?:token|access[_-]?token|bearer)\s*[:=]\s*['"]?[\w\-.]{20,}['"]?""",
        re.IGNORECASE,
    )

    MAX_CODE_LINES = 50
    MAX_SQL_LENGTH = 500

    BLOCKED_RULES: list[tuple[re.Pattern, str]] = [
        (PRIVATE_KEY_RE, "私钥 (BEGIN PRIVATE KEY)"),
        (AWS_AKIA_RE, "AWS IAM Access Key (AKIA...)"),
        (PLAINTEXT_PASSWORD_RE, "明文数据库密码 (password=...)"),
        (JDBC_PASSWORD_RE, "JDBC URL 含明文密码"),
    ]

    WARNING_RULES: list[tuple[re.Pattern, str]] = [
        (API_KEY_ASSIGN_RE, "API Key 赋值"),
        (TOKEN_ASSIGN_RE, "Token 赋值"),
    ]

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def validate(self, content: str) -> ValidationResult:
        """
        执行两级敏感信息检测。

        1. 先跑 blocked 规则 → 命中直接拒绝
        2. 再跑 warning 规则 → 命中则 risk_level=high
        3. 检测大段源码 / 大段 SQL
        """
        # Step 1: blocked
        for pattern, label in self.BLOCKED_RULES:
            if pattern.search(content):
                return ValidationResult(
                    passed=False,
                    risk_level="critical",
                    blocked=True,
                    blocked_reason=f"blocked_sensitive: {label}",
                    warnings=[f"命中 blocked 规则: {label}"],
                )

        # Step 2: warning
        warnings: list[str] = []
        risk_level = "low"

        # 大段源码检测
        lines = content.splitlines()
        code_lines = [ln for ln in lines if ln.strip() and not ln.strip().startswith("#")]
        if len(code_lines) > self.MAX_CODE_LINES:
            warnings.append(f"疑似大段源码 ({len(code_lines)} 行，超过 {self.MAX_CODE_LINES} 行限制)")
            risk_level = "high"

        # 大段 SQL 检测
        sql_indicators = (
            "SELECT ", "INSERT ", "UPDATE ", "DELETE ", "CREATE TABLE",
            "ALTER TABLE", "DROP ", "JOIN ", "FROM ", "WHERE ",
        )
        sql_hits = sum(1 for kw in sql_indicators if kw in content.upper())
        if sql_hits >= 3 and len(content) > self.MAX_SQL_LENGTH:
            warnings.append(f"疑似大段 SQL dump ({len(content)} 字符，超过 {self.MAX_SQL_LENGTH} 限制)")
            risk_level = "high"

        # 正则 warning 规则
        for pattern, label in self.WARNING_RULES:
            if pattern.search(content):
                warnings.append(f"命中 warning 规则: {label}")
                risk_level = "high"

        return ValidationResult(
            passed=True,
            risk_level=risk_level,
            blocked=False,
            warnings=warnings,
        )

    def validate_batch(self, contents: list[str]) -> list[ValidationResult]:
        """批量校验多个内容。"""
        return [self.validate(c) for c in contents]

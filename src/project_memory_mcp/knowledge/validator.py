"""ContentValidator — 敏感信息检测，两级：blocked（不保存原文）+ warning（risk_level=high）。

Phase 4.1 强化：API Key/Token/Secret/Bearer 从 warning 升级为 blocked，
新增 OpenAI/Anthropic/DeepSeek 专用 Key 检测、pwd 模式。
"""

import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """校验结果。"""
    passed: bool = True
    risk_level: str = "low"       # low|medium|high|critical
    blocked: bool = False
    blocked_reason: str = ""
    blocked_field: str = ""       # 命中的字段名（content/title/source_evidence 等）
    warnings: list[str] = field(default_factory=list)


class ContentValidator:
    """
    敏感信息检测器。

    Phase 4.1 变更：
    - API Key / Token / Secret / Bearer 从 warning 升级为 blocked
    - 新增 OpenAI / Anthropic / DeepSeek API Key、pwd 模式
    - 大段源码 / 大段 SQL 保持 warning 级别
    """

    # ── blocked 正则 ──────────────────────────────────────────────

    PRIVATE_KEY_RE = re.compile(
        r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|ENCRYPTED) PRIVATE KEY-----",
    )

    AWS_AKIA_RE = re.compile(r"AKIA[0-9A-Z]{16}")

    JDBC_PASSWORD_RE = re.compile(
        r"jdbc:[a-z]+://[^\s]*password=[^&\s]+",
        re.IGNORECASE,
    )

    # Phase 4.2: 同时支持引号和无引号，排除 ${} 占位符
    PLAINTEXT_PASSWORD_RE = re.compile(
        r"""password\s*[:=]\s*(?:['"](?!\s*\$\{)[^'"]{6,}['"]|(?!\$\{)[^\s'"&;]{6,})""",
        re.IGNORECASE,
    )

    # Phase 4.1: 升级为 blocked
    API_KEY_ASSIGN_RE = re.compile(
        r"""(?:api[_-]?key|apikey|secret[_-]?key)\s*[:=]\s*['"]?[\w\-]{20,}['"]?""",
        re.IGNORECASE,
    )

    TOKEN_ASSIGN_RE = re.compile(
        r"""(?:token|access[_-]?token|bearer)\s*[:=]\s*['"]?[\w\-.]{20,}['"]?""",
        re.IGNORECASE,
    )

    # Phase 4.1 新增 — 特定厂商 Key（唯一前缀，必须在泛化 API_KEY_ASSIGN_RE 之前）
    OPENAI_KEY_RE = re.compile(
        r"""sk-(?:proj|svcacct)-[A-Za-z0-9]{32,}""",
    )

    ANTHROPIC_KEY_RE = re.compile(
        r"""sk-ant-[A-Za-z0-9\-_]{32,}""",
    )

    DEEPSEEK_KEY_RE = re.compile(
        r"""sk-[a-z0-9]{32,}""",
    )

    # Phase 4.3: 裸 sk- key（混合大小写，不在上面特定厂商规则中命中）
    BARE_SK_KEY_RE = re.compile(
        r"""sk-[A-Za-z0-9_-]{20,}""",
    )

    SECRET_ASSIGN_RE = re.compile(
        r"""(?:secret|secret_key|private_key)\s*[:=]\s*['"]?[\w\-/+=]{20,}['"]?""",
        re.IGNORECASE,
    )

    BEARER_ASSIGN_RE = re.compile(
        r"""bearer\s+['"]?[\w\-.]{20,}['"]?""",
        re.IGNORECASE,
    )

    # Phase 4.2: 同时支持引号和无引号，排除 ${} 占位符
    PWD_ASSIGN_RE = re.compile(
        r"""\bpwd\s*[:=]\s*(?:['"](?!\s*\$\{)[^'"]{4,}['"]|(?!\$\{)[^\s'"&;]{4,})""",
        re.IGNORECASE,
    )

    # ── warning 检测阈值 ───────────────────────────────────────────

    MAX_CODE_LINES = 50
    MAX_SQL_LENGTH = 500

    # ── 规则列表 ───────────────────────────────────────────────────

    BLOCKED_RULES: list[tuple[re.Pattern, str]] = [
        (PRIVATE_KEY_RE, "私钥 (BEGIN PRIVATE KEY)"),
        (AWS_AKIA_RE, "AWS IAM Access Key (AKIA...)"),
        # 特定厂商 Key 必须在通用 API_KEY_ASSIGN_RE 之前，避免被泛化匹配吞掉
        (OPENAI_KEY_RE, "OpenAI API Key (sk-...)"),
        (ANTHROPIC_KEY_RE, "Anthropic API Key (sk-ant-...)"),
        (DEEPSEEK_KEY_RE, "DeepSeek API Key (sk-...)"),
        # Phase 4.3: 裸 sk-（混合大小写，不在上面特定厂商规则命中时兜底）
        (BARE_SK_KEY_RE, "疑似 API Key (sk-...)"),
        (JDBC_PASSWORD_RE, "JDBC URL 含明文密码"),
        (PLAINTEXT_PASSWORD_RE, "明文数据库密码 (password=...)"),
        # Phase 4.1: 从 warning 升级
        (API_KEY_ASSIGN_RE, "API Key 赋值"),
        (TOKEN_ASSIGN_RE, "Token 赋值"),
        (SECRET_ASSIGN_RE, "Secret/Private Key 赋值"),
        (BEARER_ASSIGN_RE, "Bearer Token"),
        (PWD_ASSIGN_RE, "明文密码 (pwd=...)"),
    ]

    WARNING_RULES: list[tuple[re.Pattern, str]] = [
        # 仅保留大段源码/大段 SQL 作为 warning（在 validate() 中手工检测）
    ]

    # ── 公开 API ───────────────────────────────────────────────────

    def validate(self, content: str) -> ValidationResult:
        """
        执行两级敏感信息检测。

        1. 先跑 blocked 规则 → 命中直接拒绝
        2. 再跑 warning 规则 → 命中则 risk_level=high
        3. 检测大段源码 / 大段 SQL
        """
        # Step 1: blocked
        for pattern, label in self.BLOCKED_RULES:
            m = pattern.search(content)
            if m:
                return ValidationResult(
                    passed=False,
                    risk_level="critical",
                    blocked=True,
                    blocked_reason=f"blocked_sensitive: {label}",
                    blocked_field="content",
                    warnings=[f"命中 blocked 规则: {label}"],
                )

        # Step 2: warning（大段源码 + 大段 SQL）
        warnings: list[str] = []
        risk_level = "low"

        lines = content.splitlines()
        code_lines = [ln for ln in lines if ln.strip() and not ln.strip().startswith("#")]
        if len(code_lines) > self.MAX_CODE_LINES:
            warnings.append(f"疑似大段源码 ({len(code_lines)} 行，超过 {self.MAX_CODE_LINES} 行限制)")
            risk_level = "high"

        sql_indicators = (
            "SELECT ", "INSERT ", "UPDATE ", "DELETE ", "CREATE TABLE",
            "ALTER TABLE", "DROP ", "JOIN ", "FROM ", "WHERE ",
        )
        sql_hits = sum(1 for kw in sql_indicators if kw in content.upper())
        if sql_hits >= 3 and len(content) > self.MAX_SQL_LENGTH:
            warnings.append(f"疑似大段 SQL dump ({len(content)} 字符，超过 {self.MAX_SQL_LENGTH} 限制)")
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

    # ── 全字段持久化校验 ──────────────────────────────────────────

    def validate_persisted_payload(
        self,
        title: str,
        content: str,
        source_evidence: dict | None = None,
        source_file: str | None = None,
        tags: list[str] | None = None,
    ) -> ValidationResult:
        """
        对拟持久化的全部字段执行敏感信息检测。

        检查字段：title, content, source_evidence 各字段、source_file、tags。
        命中任一字段 → blocked，返回 blocked_field 指明命中字段。
        """
        # 按优先级检查各字段
        checks = [
            ("content", content),
            ("title", title),
        ]

        if source_file:
            checks.append(("source_file", source_file))

        if source_evidence:
            checks.extend(self._walk_source_evidence(source_evidence, "source_evidence"))

        if tags:
            for i, tag in enumerate(tags):
                if tag and isinstance(tag, str):
                    checks.append((f"tags[{i}]", tag))

        final_result = ValidationResult(passed=True, risk_level="low")

        for field_name, text in checks:
            result = self.validate(text)
            if result.blocked:
                result.blocked_field = field_name
                return result
            # 传播 warning 和 risk_level（取最高）
            if result.risk_level == "high":
                final_result.risk_level = "high"
            final_result.warnings.extend(result.warnings)

        return final_result

    # ── 递归扫描 source_evidence ───────────────────────────────────

    # Phase 4.3: key 路径使用 $ 前缀区分（$key vs .value）
    KEY_PATH_SEP = "$"

    def _walk_source_evidence(
        self, obj, prefix: str
    ) -> list[tuple[str, str]]:
        """
        递归遍历 source_evidence 中所有字符串值 + 所有 dict key。

        返回 [(field_path, text), ...]。
        value 路径: source_evidence.nested.raw
        key 路径:   source_evidence.$keyName（Phase 4.3 新增）
        list 路径:  source_evidence.items[0].context
        """
        results: list[tuple[str, str]] = []
        if isinstance(obj, dict):
            for key, value in obj.items():
                val_path = f"{prefix}.{key}"
                # Phase 4.3: dict key 也参与敏感信息扫描
                if isinstance(key, str):
                    key_path = f"{prefix}.{self.KEY_PATH_SEP}{key}"
                    results.append((key_path, key))
                if isinstance(value, str):
                    results.append((val_path, value))
                elif isinstance(value, dict):
                    results.extend(self._walk_source_evidence(value, val_path))
                elif isinstance(value, list):
                    results.extend(self._walk_source_evidence(value, val_path))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                idx_path = f"{prefix}[{i}]"
                if isinstance(item, str):
                    results.append((idx_path, item))
                elif isinstance(item, dict):
                    # Phase 4.3: list 内 dict 的 key 也扫描
                    for key, value in item.items():
                        if isinstance(key, str):
                            key_path = f"{idx_path}.{self.KEY_PATH_SEP}{key}"
                            results.append((key_path, key))
                        val_path = f"{idx_path}.{key}"
                        if isinstance(value, str):
                            results.append((val_path, value))
                        elif isinstance(value, (dict, list)):
                            results.extend(self._walk_source_evidence(value, val_path))
                elif isinstance(item, list):
                    results.extend(self._walk_source_evidence(item, idx_path))
        return results

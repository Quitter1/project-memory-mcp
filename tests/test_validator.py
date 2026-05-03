"""ContentValidator 测试 — blocked/warning 两级检测 + 全字段校验。

Phase 4.1 更新：API Key/Token/Secret/Bearer 从 warning 升级为 blocked，
新增 OpenAI/Anthropic/DeepSeek Key、pwd 检测、validate_persisted_payload。
"""

import pytest

from project_memory_mcp.knowledge.validator import ContentValidator, ValidationResult


@pytest.fixture
def validator():
    return ContentValidator()


# ==================================================================
# Blocked 级别 — Phase 4.1 强化
# ==================================================================

class TestBlocked:
    """blocked 级别 — 不保存原文。"""

    def test_01_clean_content_passes(self, validator):
        result = validator.validate("订单查询接口需要添加 @Transactional 注解")
        assert result.passed is True
        assert result.blocked is False
        assert result.risk_level == "low"
        assert result.warnings == []

    def test_02_private_key_blocked(self, validator):
        content = """-----BEGIN RSA PRIVATE KEY-----
MIICXAIBAAKBgQC...
-----END RSA PRIVATE KEY-----"""
        result = validator.validate(content)
        assert result.passed is False
        assert result.blocked is True
        assert "私钥" in result.blocked_reason
        assert result.blocked_field == "content"

    def test_03_aws_akia_blocked(self, validator):
        result = validator.validate("AWS key: AKIA1234567890ABCDEF with secret")
        assert result.passed is False
        assert result.blocked is True
        assert "AKIA" in result.blocked_reason

    def test_04_plaintext_password_blocked(self, validator):
        result = validator.validate('database password="myP@ssw0rd123" for prod')
        assert result.passed is False
        assert result.blocked is True
        assert "密码" in result.blocked_reason

    def test_05_placeholder_password_passes(self, validator):
        """password=${ENV_VAR} 占位符不应被 blocked。"""
        result = validator.validate('database password="${DB_PASSWORD}" for prod')
        assert result.blocked is False

    def test_06_jdbc_password_blocked(self, validator):
        result = validator.validate(
            "jdbc:mysql://localhost:3306/db?password=secret123&user=admin"
        )
        assert result.passed is False
        assert result.blocked is True
        assert "JDBC" in result.blocked_reason

    def test_07_ec_private_key_blocked(self, validator):
        content = "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEE..."
        result = validator.validate(content)
        assert result.blocked is True

    def test_08_encrypted_private_key_blocked(self, validator):
        content = "-----BEGIN ENCRYPTED PRIVATE KEY-----\nMIIC..."
        result = validator.validate(content)
        assert result.blocked is True

    # ── Phase 4.1: 从 warning 升级为 blocked ──

    def test_09_api_key_blocked(self, validator):
        result = validator.validate(
            'api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"'
        )
        assert result.passed is False
        assert result.blocked is True
        assert result.blocked_field == "content"
        assert "API Key" in result.blocked_reason

    def test_10_token_blocked(self, validator):
        result = validator.validate(
            'token = "ghp_abcdefghijklmnopqrstuvwxyz"'
        )
        assert result.passed is False
        assert result.blocked is True
        assert "Token" in result.blocked_reason

    # ── Phase 4.1 新增 blocked 规则 ──

    def test_11_openai_key_blocked(self, validator):
        result = validator.validate(
            'OPENAI_API_KEY = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890"'
        )
        assert result.passed is False
        assert result.blocked is True
        assert "OpenAI" in result.blocked_reason

    def test_12_anthropic_key_blocked(self, validator):
        result = validator.validate(
            'ANTHROPIC_API_KEY = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz123456"'
        )
        assert result.passed is False
        assert result.blocked is True
        assert "Anthropic" in result.blocked_reason

    def test_13_deepseek_key_blocked(self, validator):
        result = validator.validate(
            'DEEPSEEK_API_KEY = "sk-abcdefghijklmnopqrstuvwxyz123456"'
        )
        assert result.passed is False
        assert result.blocked is True
        assert "DeepSeek" in result.blocked_reason

    def test_14_secret_assign_blocked(self, validator):
        result = validator.validate(
            'secret = "my-super-secret-value-1234567890"'
        )
        assert result.passed is False
        assert result.blocked is True
        assert "Secret" in result.blocked_reason

    def test_15_bearer_token_blocked(self, validator):
        result = validator.validate(
            'Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
        )
        assert result.passed is False
        assert result.blocked is True
        assert "Bearer" in result.blocked_reason

    def test_16_pwd_assign_blocked(self, validator):
        result = validator.validate('pwd = "SuperSecret123"')
        assert result.passed is False
        assert result.blocked is True
        assert "pwd" in result.blocked_reason.lower() or "密码" in result.blocked_reason

    # ── Phase 4.2: 无引号 password/pwd blocked ──

    def test_17_password_unquoted_blocked(self, validator):
        result = validator.validate("database password=secret123 config")
        assert result.passed is False
        assert result.blocked is True

    def test_18_password_colon_unquoted_blocked(self, validator):
        result = validator.validate("db connection password: secret123")
        assert result.passed is False
        assert result.blocked is True

    def test_19_pwd_unquoted_blocked(self, validator):
        result = validator.validate("db pwd=secret123 config")
        assert result.passed is False
        assert result.blocked is True

    def test_20_pwd_colon_unquoted_blocked(self, validator):
        result = validator.validate("db connection pwd: secret123")
        assert result.passed is False
        assert result.blocked is True

    def test_21_password_placeholder_not_blocked(self, validator):
        result = validator.validate("database password=${DB_PASSWORD}")
        assert result.blocked is False

    def test_22_pwd_placeholder_not_blocked(self, validator):
        result = validator.validate("db pwd=${DB_PASSWORD}")
        assert result.blocked is False

    def test_23_password_quoted_placeholder_not_blocked(self, validator):
        result = validator.validate('database password="${DB_PASSWORD}"')
        assert result.blocked is False

    def test_24_pwd_quoted_placeholder_not_blocked(self, validator):
        result = validator.validate('db pwd="${DB_PASSWORD}"')
        assert result.blocked is False

    # ── Phase 4.3: 裸 sk- 混合大小写检测 ──

    def test_25_bare_sk_mixed_case_blocked(self, validator):
        result = validator.validate("default key: sk-abcDEF1234567890abcDEF1234567890")
        assert result.blocked is True

    def test_26_api_key_equals_sk_mixed_blocked(self, validator):
        result = validator.validate(
            "OPENAI_API_KEY=sk-abcDEF1234567890abcDEF1234567890 in config"
        )
        assert result.blocked is True


# ==================================================================
# Warning 级别 — Phase 4.1: 仅保留大段源码/大段 SQL
# ==================================================================

class TestWarning:
    """warning 级别 — risk_level=high，强制 pending_review。"""

    def test_17_large_code_warning(self, validator):
        """超过 50 行代码触发 warning。"""
        lines = []
        for i in range(55):
            lines.append(f"    result = process_item(item_{i})")
        content = "def process_all(items):\n" + "\n".join(lines)
        result = validator.validate(content)
        assert result.blocked is False
        assert result.risk_level == "high"
        assert any("大段源码" in w for w in result.warnings)

    def test_18_code_under_50_lines_passes(self, validator):
        """不超过 50 行代码不触发 warning。"""
        lines = []
        for i in range(30):
            lines.append(f"    x = {i}")
        content = "def foo():\n" + "\n".join(lines)
        result = validator.validate(content)
        assert result.blocked is False
        assert result.risk_level == "low"

    def test_19_large_sql_warning(self, validator):
        """超过 500 字符且含 SQL 关键词触发 warning。"""
        sql = (
            "SELECT id, name, value, created_at, updated_at "
            "FROM orders WHERE status = 'active' "
            "AND type IN ('a', 'b', 'c') "
        ) * 8
        sql += " OR customer_id IN (SELECT id FROM customers WHERE region = 'CN')"
        assert len(sql) > 500
        result = validator.validate(sql)
        assert result.blocked is False
        assert result.risk_level == "high"
        assert any("SQL" in w for w in result.warnings)

    def test_20_short_sql_passes(self, validator):
        """不超过 500 字符的 SQL 不触发 warning。"""
        sql = "SELECT id, name FROM orders WHERE id = 1"
        result = validator.validate(sql)
        assert result.blocked is False
        assert result.risk_level == "low"


# ==================================================================
# 批量校验
# ==================================================================

class TestBatch:
    """批量校验。"""

    def test_21_validate_batch(self, validator):
        results = validator.validate_batch([
            "normal content here",
            "-----BEGIN RSA PRIVATE KEY----- blocked",
            # Phase 4.1: api_key 从 warning 升级为 blocked，仍被 blocked
            "api_key = 'sk-12345678901234567890' is now blocked too",
        ])
        assert len(results) == 3
        assert results[0].passed is True and results[0].blocked is False
        assert results[1].blocked is True
        assert results[2].blocked is True  # Phase 4.1: 升级为 blocked


# ==================================================================
# Phase 4.1: validate_persisted_payload 全字段校验
# ==================================================================

class TestPersistedPayload:
    """全字段持久化校验测试。"""

    def test_22_clean_payload_passes(self, validator):
        result = validator.validate_persisted_payload(
            title="订单查询接口规范",
            content="订单查询接口需要添加 @Transactional 注解确保事务一致性",
            source_evidence={
                "file": "OrderController.java",
                "excerpt": "@GetMapping(\"/query\")",
                "reasoning": "缺少事务注解",
            },
            source_file="OrderController.java",
            tags=["order", "transaction"],
        )
        assert result.passed is True
        assert result.blocked is False

    def test_23_sensitive_in_title_blocked(self, validator):
        result = validator.validate_persisted_payload(
            title='api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"',
            content="安全的正文内容",
        )
        assert result.blocked is True
        assert result.blocked_field == "title"

    def test_24_sensitive_in_source_evidence_blocked(self, validator):
        result = validator.validate_persisted_payload(
            title="安全的标题",
            content="安全的正文内容",
            source_evidence={
                "excerpt": 'token = "ghp_abcdefghijklmnopqrstuvwxyz"',
            },
        )
        assert result.blocked is True
        assert "source_evidence.excerpt" in result.blocked_field

    def test_25_sensitive_in_tags_blocked(self, validator):
        result = validator.validate_persisted_payload(
            title="安全的标题",
            content="安全的正文内容",
            tags=["order", "AKIA1234567890ABCDEF"],
        )
        assert result.blocked is True
        assert "tags[1]" in result.blocked_field

    def test_26_sensitive_in_source_file_blocked(self, validator):
        result = validator.validate_persisted_payload(
            title="安全的标题",
            content="安全的正文内容",
            source_file="AKIA1234567890ABCDEF.config",
        )
        assert result.blocked is True
        assert "source_file" in result.blocked_field

    # ── Phase 4.2: 递归扫描 source_evidence ──

    def test_27_snippet_with_api_key_blocked(self, validator):
        result = validator.validate_persisted_payload(
            title="安全的标题",
            content="安全的正文",
            source_evidence={
                "snippet": 'OPENAI_API_KEY = "sk-proj-abcdefghijklmnopqrstuvwxyz123456"',
            },
        )
        assert result.blocked is True
        assert "source_evidence.snippet" in result.blocked_field

    def test_28_nested_raw_with_token_blocked(self, validator):
        result = validator.validate_persisted_payload(
            title="安全的标题",
            content="安全的正文",
            source_evidence={
                "result": {
                    "nested": {
                        "raw": "token=ghp_abcdefghijklmnopqrstuvwxyz",
                    },
                },
            },
        )
        assert result.blocked is True
        assert "source_evidence.result.nested.raw" in result.blocked_field

    def test_29_items_context_with_password_blocked(self, validator):
        result = validator.validate_persisted_payload(
            title="安全的标题",
            content="安全的正文",
            source_evidence={
                "items": [
                    {"context": "password=secret123"},
                ],
            },
        )
        assert result.blocked is True
        assert "source_evidence.items[0].context" in result.blocked_field

    def test_30_recursive_blocked_field_path(self, validator):
        result = validator.validate_persisted_payload(
            title="安全的标题",
            content="安全的正文",
            source_evidence={
                "deep": {
                    "list": [
                        {"key": "safe"},
                        {"secret": 'api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"'},
                    ],
                },
            },
        )
        assert result.blocked is True
        assert "source_evidence.deep.list[1].secret" in result.blocked_field

    # ── Phase 4.3: source_evidence key 也扫描 ──

    def test_31_top_level_key_with_api_key_blocked(self, validator):
        result = validator.validate_persisted_payload(
            title="安全的标题",
            content="安全的正文",
            source_evidence={
                "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456": "safe",
            },
        )
        assert result.blocked is True
        assert "$OPENAI_API_KEY" in result.blocked_field

    def test_32_nested_key_with_token_blocked(self, validator):
        result = validator.validate_persisted_payload(
            title="安全的标题",
            content="安全的正文",
            source_evidence={
                "nested": {
                    "token=ghp_abcdefghijklmnopqrstuvwxyz": "safe",
                },
            },
        )
        assert result.blocked is True
        assert "$token" in result.blocked_field
        assert "nested" in result.blocked_field

    def test_33_list_dict_key_with_password_blocked(self, validator):
        result = validator.validate_persisted_payload(
            title="安全的标题",
            content="安全的正文",
            source_evidence={
                "items": [
                    {"password=secret123": "safe"},
                ],
            },
        )
        assert result.blocked is True
        assert "$password" in result.blocked_field
        assert "items[0]" in result.blocked_field

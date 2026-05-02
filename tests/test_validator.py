"""ContentValidator 测试 — blocked/warning 两级检测。"""

import pytest

from project_memory_mcp.knowledge.validator import ContentValidator, ValidationResult


@pytest.fixture
def validator():
    return ContentValidator()


# ------------------------------------------------------------------
# Blocked 级别
# ------------------------------------------------------------------

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


# ------------------------------------------------------------------
# Warning 级别
# ------------------------------------------------------------------

class TestWarning:
    """warning 级别 — risk_level=high，强制 pending_review。"""

    def test_09_api_key_warning(self, validator):
        result = validator.validate(
            'api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"'
        )
        assert result.passed is True
        assert result.blocked is False
        assert result.risk_level == "high"
        assert any("API Key" in w for w in result.warnings)

    def test_10_token_warning(self, validator):
        result = validator.validate(
            'token = "ghp_abcdefghijklmnopqrstuvwxyz"'
        )
        assert result.passed is True
        assert result.risk_level == "high"
        assert any("Token" in w for w in result.warnings)

    def test_11_large_code_warning(self, validator):
        """超过 50 行代码触发 warning。"""
        lines = []
        for i in range(55):
            lines.append(f"    result = process_item(item_{i})")
        content = "def process_all(items):\n" + "\n".join(lines)
        result = validator.validate(content)
        assert result.risk_level == "high"
        assert any("大段源码" in w for w in result.warnings)

    def test_12_code_under_50_lines_passes(self, validator):
        """不超过 50 行代码不触发 warning。"""
        lines = []
        for i in range(30):
            lines.append(f"    x = {i}")
        content = "def foo():\n" + "\n".join(lines)
        result = validator.validate(content)
        assert result.risk_level == "low"

    def test_13_large_sql_warning(self, validator):
        """超过 500 字符且含 SQL 关键词触发 warning。"""
        sql = (
            "SELECT id, name, value, created_at, updated_at "
            "FROM orders WHERE status = 'active' "
            "AND type IN ('a', 'b', 'c') "
        ) * 8
        sql += " OR customer_id IN (SELECT id FROM customers WHERE region = 'CN')"
        assert len(sql) > 500
        result = validator.validate(sql)
        assert result.risk_level == "high"
        assert any("SQL" in w for w in result.warnings)

    def test_14_short_sql_passes(self, validator):
        """不超过 500 字符的 SQL 不触发 warning。"""
        sql = "SELECT id, name FROM orders WHERE id = 1"
        result = validator.validate(sql)
        assert result.risk_level == "low"

    def test_15_bearer_token_warning(self, validator):
        result = validator.validate(
            'bearer = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."'
        )
        assert result.risk_level == "high"

    def test_16_combined_warnings(self, validator):
        """同时命中多个 warning 规则。"""
        content = (
            'api_key = "sk-longerthan20characters!!!" '
            'and token = "tk-longerthan20chars!!"'
        )
        result = validator.validate(content)
        assert result.risk_level == "high"
        assert len(result.warnings) >= 2


# ------------------------------------------------------------------
# 批量校验
# ------------------------------------------------------------------

class TestBatch:
    """批量校验。"""

    def test_17_validate_batch(self, validator):
        results = validator.validate_batch([
            "normal content here",
            "-----BEGIN RSA PRIVATE KEY----- blocked",
            "api_key = 'sk-12345678901234567890' warning",
        ])
        assert len(results) == 3
        assert results[0].passed is True and results[0].blocked is False
        assert results[1].blocked is True
        assert results[2].risk_level == "high"

"""
Phase 14 文档存在性 + 内容检查。
"""

from pathlib import Path

_DOCS = Path(__file__).parent.parent / "docs"
_OPS = _DOCS.parent / "scripts" / "ops"


def test_deployment_exists():
    assert (_DOCS / "部署指南.md").exists()


def test_agent_usage_guide_exists():
    assert (_DOCS / "Agent使用规范.md").exists()


def test_agent_skill_template_exists():
    assert (_DOCS / "Agent技能模板.md").exists()


def test_production_checklist_exists():
    assert (_DOCS / "正式使用检查清单.md").exists()


def test_skill_template_forbids_api_key():
    content = (_DOCS / "Agent技能模板.md").read_text(encoding="utf-8")
    assert "API Key" in content or "禁止" in content


def test_skill_template_has_search_then_propose():
    content = (_DOCS / "Agent技能模板.md").read_text(encoding="utf-8")
    assert "search_project_context" in content or "propose_memory" in content


def test_production_checklist_has_backup():
    content = (_DOCS / "正式使用检查清单.md").read_text(encoding="utf-8")
    assert "备份" in content


def test_cc_setup_has_kill_mcp():
    content = (_DOCS / "ClaudeCode接入配置.md").read_text(encoding="utf-8")
    assert "kill_mcp_processes" in content or "Kill" in content


def test_ops_health_check_exists():
    assert (_OPS / "health_check.ps1").exists()


def test_ops_backup_exists():
    assert (_OPS / "backup_memory_db.ps1").exists()


def test_ops_e2e_exists():
    assert (_OPS / "e2e_usage_check.ps1").exists()


def test_backup_script_no_api_key():
    content = (_OPS / "backup_memory_db.ps1").read_text(encoding="utf-8")
    assert "sk-" not in content


def test_agent_guide_forbids_auto_propose():
    content = (_DOCS / "Agent使用规范.md").read_text(encoding="utf-8")
    assert "自动" in content or "默认禁止" in content

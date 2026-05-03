"""
日志测试 — setup_logging, redaction, ToolHandler 日志, 敏感信息不进日志。
"""

import tempfile
from pathlib import Path

import pytest

from project_memory_mcp.utils.logging import (
    setup_logging, redact_sensitive, sanitize_for_log, new_request_id,
)


def test_setup_logging_creates_files():
    import project_memory_mcp.utils.logging as ulog
    ulog._current_config = None

    tmp = Path(tempfile.mkdtemp())
    log_dir = tmp / "logs"
    logger = ulog.setup_logging(log_dir=log_dir, level="INFO", enable_file=True)
    logger.info("test message")
    logger.error("force error log for file creation")

    assert (log_dir / "project-memory-mcp.log").exists()
    assert (log_dir / "errors.log").exists()
    content = (log_dir / "project-memory-mcp.log").read_text(encoding="utf-8")
    assert "test message" in content


def test_setup_logging_idempotent():
    import project_memory_mcp.utils.logging as ulog
    ulog._current_config = None

    tmp = Path(tempfile.mkdtemp())
    log_dir = tmp / "logs"
    logger1 = ulog.setup_logging(log_dir=log_dir, level="INFO", enable_file=True)
    logger2 = ulog.setup_logging(log_dir=log_dir, level="INFO", enable_file=True)
    assert logger1 is logger2
    logger1.info("only once")
    content = (log_dir / "project-memory-mcp.log").read_text(encoding="utf-8")
    assert content.count("only once") == 1


def test_redact_sk_key():
    assert "sk-[REDACTED]" in redact_sensitive("api_key=sk-abcdefghijklmnopqrstuvwxyz123456")
    # key 名保留，value 脱敏
    result = redact_sensitive("OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456")
    assert "sk-proj" not in result
    assert "OPENAI_API_KEY" in result  # key 名本身不敏感


def test_redact_password():
    assert "password=[REDACTED]" in redact_sensitive("password=secret123")


def test_redact_token():
    assert "token=[REDACTED]" in redact_sensitive("token=ghp_abcdefghijklmnopqrstuvwxyz")


def test_redact_bearer():
    assert "bearer [REDACTED]" in redact_sensitive("Authorization: bearer eyJhbGciOiJIUzI1NiIs...")


def test_redact_aws_key():
    assert "AKIA[REDACTED]" in redact_sensitive("AWS key: AKIA1234567890ABCDEF")


def test_sanitize_truncates():
    long_text = "x" * 120
    result = sanitize_for_log(long_text, max_len=80)
    assert len(result) <= 83  # "..." 额外 3 字符


def test_new_request_id_format():
    rid = new_request_id()
    assert rid.startswith("req_")
    assert len(rid) == 12  # req_ + 8 hex


# ── ToolHandler 日志集成 ─────────────────────────────────────

def _write_projects_yml(config_dir: Path):
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "projects.yml").write_text("""\
projects:
  test-proj:
    name: "测试"
    slug: "test-proj"
    status: active
    recognition:
      root_paths: ["/test"]
      aliases: ["test"]
defaults:
  knowledge_policy:
    auto_approve_threshold: -1
    max_candidate_per_task: 20
    retention_days: 365
  review_policy:
    allow_ai_auto_approve: false
    forbidden_auto_types: []
    risk_threshold_for_review: medium
    require_review_if_conflict: true
""", encoding="utf-8")


@pytest.fixture
def ctx_with_log():
    import project_memory_mcp.utils.logging as ulog
    ulog._current_config = None

    tmp = Path(tempfile.mkdtemp())
    config_dir = tmp / "config"
    db_path = tmp / "memory.db"
    log_dir = tmp / "logs"
    _write_projects_yml(config_dir)

    import os
    os.environ["PROJECT_MEMORY_LOG_DIR"] = str(log_dir)

    from project_memory_mcp.app_context import AppContext
    c = AppContext(config_dir=config_dir, db_path=db_path)
    c.sync_projects()
    yield c, log_dir
    c.db.close()
    import shutil
    shutil.rmtree(str(tmp), ignore_errors=True)


def test_tool_handler_writes_logs(ctx_with_log):
    ctx, log_dir = ctx_with_log
    from project_memory_mcp.tools.handlers import ToolHandler
    handler = ToolHandler(ctx)
    handler.list_projects({})

    log_content = (log_dir / "project-memory-mcp.log").read_text(encoding="utf-8")
    assert "tool_start" in log_content
    assert "tool_success" in log_content
    assert "request_id" in log_content


def test_propose_sensitive_not_in_log(ctx_with_log):
    ctx, log_dir = ctx_with_log
    from project_memory_mcp.tools.handlers import ToolHandler
    handler = ToolHandler(ctx)
    handler.propose_memory({
        "project_id": "test-proj",
        "title": "API Key 泄露测试",
        "content": "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456",
        "actor": "test",
    })

    log_content = (log_dir / "project-memory-mcp.log").read_text(encoding="utf-8")
    assert "sk-proj" not in log_content
    assert "OPENAI_API_KEY" not in log_content
    assert "governance_decision" in log_content


def test_search_query_not_in_log(ctx_with_log):
    ctx, log_dir = ctx_with_log
    from project_memory_mcp.tools.handlers import ToolHandler
    handler = ToolHandler(ctx)
    handler.search_project_context({
        "project_id": "test-proj",
        "query": "sk-proj-abcdefghijklmnopqrstuvwxyz123456",
    })

    log_content = (log_dir / "project-memory-mcp.log").read_text(encoding="utf-8")
    assert "sk-proj" not in log_content
    assert "query_length" in log_content


# ── Phase 6.5: setup_logging 重配 ────────────────────────────

def test_setup_logging_different_dir_switches():
    import logging as _logging_
    import project_memory_mcp.utils.logging as ulog
    ulog._current_config = None

    tmp_a = Path(tempfile.mkdtemp())
    tmp_b = Path(tempfile.mkdtemp())
    log_a = tmp_a / "logs"
    log_b = tmp_b / "logs"

    ulog.setup_logging(log_dir=log_a, level="INFO")
    _logging_.getLogger("project_memory_mcp").info("msg in A")
    assert (log_a / "project-memory-mcp.log").exists()

    ulog.setup_logging(log_dir=log_b, level="INFO")
    _logging_.getLogger("project_memory_mcp").info("msg in B")
    assert (log_b / "project-memory-mcp.log").exists()

    # A 不应再收到新日志
    content_a = (log_a / "project-memory-mcp.log").read_text(encoding="utf-8")
    assert "msg in B" not in content_a


def test_setup_logging_same_dir_no_duplicate():
    import logging as _logging_
    import project_memory_mcp.utils.logging as ulog
    ulog._current_config = None

    tmp = Path(tempfile.mkdtemp())
    log_dir = tmp / "logs"
    ulog.setup_logging(log_dir=log_dir, level="INFO")
    ulog.setup_logging(log_dir=log_dir, level="INFO")
    _logging_.getLogger("project_memory_mcp").info("once")
    content = (log_dir / "project-memory-mcp.log").read_text(encoding="utf-8")
    assert content.count("once") == 1


# ── Phase 6.5: server.yml logging ────────────────────────────

def _write_server_yml(config_dir: Path, extra: str = ""):
    (config_dir / "server.yml").write_text(f"""\
server:
  name: test
  version: "0.1"
{extra}
""", encoding="utf-8")


def test_server_yml_logging_config():
    import project_memory_mcp.utils.logging as ulog
    ulog._current_config = None
    import os
    os.environ.pop("PROJECT_MEMORY_LOG_DIR", None)

    tmp = Path(tempfile.mkdtemp())
    config_dir = tmp / "config"
    _write_projects_yml(config_dir)
    _write_server_yml(config_dir, """
logging:
  level: "DEBUG"
  log_dir: "custom_logs"
""")
    from project_memory_mcp.app_context import AppContext
    ctx = AppContext(config_dir=config_dir, db_path=tmp / "memory.db")
    custom_dir = tmp / "custom_logs"
    assert custom_dir.exists()
    ctx.db.close()


def test_server_yml_file_enabled_false():
    import project_memory_mcp.utils.logging as ulog
    ulog._current_config = None
    import os
    os.environ.pop("PROJECT_MEMORY_LOG_DIR", None)

    tmp = Path(tempfile.mkdtemp())
    config_dir = tmp / "config"
    _write_projects_yml(config_dir)
    _write_server_yml(config_dir, """
logging:
  file_enabled: false
""")
    from project_memory_mcp.app_context import AppContext
    ctx = AppContext(config_dir=config_dir, db_path=tmp / "memory.db")
    # 默认 logs/ 不应创建（file_enabled=false）
    default_logs = tmp / "logs"
    assert not (default_logs / "project-memory-mcp.log").exists()
    ctx.db.close()


# ── Phase 6.5: app_context_ready ────────────────────────────

def test_app_context_ready_log():
    import project_memory_mcp.utils.logging as ulog
    ulog._current_config = None
    import os
    os.environ.pop("PROJECT_MEMORY_LOG_DIR", None)

    tmp = Path(tempfile.mkdtemp())
    config_dir = tmp / "config"
    db_path = tmp / "memory.db"
    log_dir = tmp / "logs"
    _write_projects_yml(config_dir)
    os.environ["PROJECT_MEMORY_LOG_DIR"] = str(log_dir)
    from project_memory_mcp.app_context import AppContext
    ctx = AppContext(config_dir=config_dir, db_path=db_path)
    ctx.db.close()

    content = (log_dir / "project-memory-mcp.log").read_text(encoding="utf-8")
    assert "app_context_ready" in content
    assert "user_version=" in content
    assert "project_count=" in content


# ── Phase 6.5: governance_decision defaults ──────────────────

def test_governance_decision_defaults(ctx_with_log):
    ctx, log_dir = ctx_with_log
    from project_memory_mcp.tools.handlers import ToolHandler
    handler = ToolHandler(ctx)
    handler.propose_memory({
        "project_id": "test-proj",
        "title": "test", "content": "safe",
        # 不传 scope/source_type
        "actor": "test",
    })
    content = (log_dir / "project-memory-mcp.log").read_text(encoding="utf-8")
    assert "source_type=ai_inferred" in content
    assert "scope=project" in content
    assert "source_type=?" not in content
    assert "scope=?" not in content

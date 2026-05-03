"""MCP tools 集成测试 — 测试所有 9 个 tool handler。

不通过 MCP stdio，直接调用 ToolHandler 方法验证行为。
"""

import os
import tempfile
from pathlib import Path

import pytest

from project_memory_mcp.app_context import AppContext
from project_memory_mcp.tools.handlers import ToolHandler, make_response, make_error_response


# ── helpers ────────────────────────────────────────────────────

def _write_projects_yml(config_dir: Path):
    """写入最小测试用 projects.yml。"""
    config_dir.mkdir(parents=True, exist_ok=True)
    yml = config_dir / "projects.yml"
    yml.write_text("""\
projects:
  test-proj:
    name: "测试项目"
    slug: "test-proj"
    status: active
    recognition:
      root_paths:
        - "/test/proj"
      aliases:
        - "test"
      tech_stack_keywords:
        - "python"
    knowledge_policy:
      auto_approve_threshold: 0.8
    review_policy:
      allow_ai_auto_approve: false
  proj2:
    name: "项目二"
    slug: "proj2"
    status: active
    recognition:
      root_paths:
        - "/test/proj2"
      aliases:
        - "p2"
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


# ── fixtures ────────────────────────────────────────────────────

@pytest.fixture
def ctx():
    """创建测试用 AppContext。"""
    tmp = Path(tempfile.mkdtemp())
    config_dir = tmp / "config"
    db_path = tmp / "memory.db"
    _write_projects_yml(config_dir)
    c = AppContext(config_dir=config_dir, db_path=db_path)
    c.sync_projects()
    yield c
    c.db.close()
    for f in tmp.glob("*.db*"):
        f.unlink(missing_ok=True)
    import shutil
    shutil.rmtree(str(tmp), ignore_errors=True)


@pytest.fixture
def handler(ctx):
    return ToolHandler(ctx)


# ── 1. list_projects ──────────────────────────────────────────

def test_list_projects_active(handler):
    r = handler.list_projects({"status_filter": "active"})
    assert r["ok"] is True
    assert len(r["data"]["projects"]) >= 2
    slugs = [p["slug"] for p in r["data"]["projects"]]
    assert "test-proj" in slugs


def test_list_projects_all(handler):
    r = handler.list_projects({"status_filter": ""})
    assert r["ok"] is True
    assert r["data"]["total"] >= 2


# ── 2. resolve_project ─────────────────────────────────────────

def test_resolve_explicit_id(handler):
    r = handler.resolve_project({"project_id": "test-proj"})
    assert r["ok"] is True
    assert r["data"]["resolved"] is True
    assert r["data"]["project"]["slug"] == "test-proj"


def test_resolve_not_found(handler):
    r = handler.resolve_project({"project_id": "nonexistent"})
    assert r["ok"] is False
    assert r["error"]["code"] == "project_not_found"


# ── 3. get_project_profile ────────────────────────────────────

def test_get_project_profile(handler):
    r = handler.get_project_profile({"project_id": "test-proj"})
    assert r["ok"] is True
    assert r["data"]["project"]["slug"] == "test-proj"
    assert "total_memories" in r["data"]["stats"]


def test_get_project_profile_missing_id(handler):
    r = handler.get_project_profile({"project_id": ""})
    assert r["ok"] is False
    assert r["error"]["code"] == "invalid_params"


# ── 4. search_project_context ─────────────────────────────────

def test_search_project_context(handler):
    r = handler.search_project_context({
        "project_id": "test-proj",
        "query": "订单",
    })
    assert r["ok"] is True
    assert "context_pack" in r["data"]


def test_search_no_project_id_returns_error(handler):
    r = handler.search_project_context({"query": "test"})
    assert r["ok"] is False
    assert r["error"]["code"] == "project_id_required"


# ── 5. propose_memory ─────────────────────────────────────────

def test_propose_normal(handler):
    r = handler.propose_memory({
        "project_id": "test-proj",
        "title": "订单查询接口规范",
        "content": "需要添加 @Transactional 注解",
        "type": "api",
        "confidence": 0.5,
        "source_type": "ai_inferred",
        "actor": "test",
    })
    assert r["ok"] is True
    assert r["data"]["status"] == "pending_review"
    assert r["data"]["memory_id"] != ""


def test_propose_blocked_api_key(handler):
    r = handler.propose_memory({
        "project_id": "test-proj",
        "title": "包含私钥",
        "content": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...",
        "actor": "test",
    })
    assert r["ok"] is True
    assert r["data"]["status"] == "rejected"
    assert r["data"]["memory_id"] == ""
    assert r["data"]["validation"]["blocked"] is True


def test_propose_missing_project(handler):
    r = handler.propose_memory({
        "title": "test",
        "content": "content",
    })
    assert r["ok"] is False
    assert r["error"]["code"] == "project_id_required"


# ── 6. list_memories ──────────────────────────────────────────

def test_list_memories(handler):
    r = handler.list_memories({"project_id": "test-proj"})
    assert r["ok"] is True
    assert "memories" in r["data"]


def test_list_memories_missing_project(handler):
    r = handler.list_memories({"project_id": ""})
    assert r["ok"] is False


# ── 7. approve_memory ─────────────────────────────────────────

def test_approve_memory(handler):
    pr = handler.propose_memory({
        "project_id": "test-proj",
        "title": "待批准的知识",
        "content": "测试内容",
        "confidence": 0.5,
        "source_type": "ai_inferred",
        "actor": "test",
    })
    mid = pr["data"]["memory_id"]

    r = handler.approve_memory({
        "memory_id": mid,
        "reviewer": "admin",
        "comment": "确认正确",
    })
    assert r["ok"] is True
    assert r["data"]["status"] == "approved"


def test_approve_invalid_memory(handler):
    r = handler.approve_memory({"memory_id": "nonexistent"})
    assert r["ok"] is False
    assert r["error"]["code"] == "memory_not_found"


# ── 8. reject_memory ─────────────────────────────────────────

def test_reject_memory(handler):
    pr = handler.propose_memory({
        "project_id": "test-proj",
        "title": "待拒绝的知识",
        "content": "测试内容",
        "confidence": 0.5,
        "source_type": "ai_inferred",
        "actor": "test",
    })
    mid = pr["data"]["memory_id"]

    r = handler.reject_memory({
        "memory_id": mid,
        "reviewer": "admin",
        "reason": "信息不准确",
    })
    assert r["ok"] is True
    assert r["data"]["status"] == "rejected"


# ── 9. deprecate_memory ───────────────────────────────────────

def test_deprecate_memory(handler):
    pr = handler.propose_memory({
        "project_id": "test-proj",
        "title": "待废弃的知识",
        "content": "测试内容",
        "confidence": 0.9,
        "source_type": "user_confirmed",
        "actor": "test",
    })
    mid = pr["data"]["memory_id"]

    handler.approve_memory({"memory_id": mid, "reviewer": "admin"})

    r = handler.deprecate_memory({
        "memory_id": mid,
        "reason": "接口已重构",
    })
    assert r["ok"] is True
    assert r["data"]["status"] == "deprecated"


# ── 10. 错误格式 ──────────────────────────────────────────────

def test_all_fields_have_ok(handler):
    assert "ok" in handler.list_projects({})
    assert "ok" in handler.resolve_project({"project_id": "test"})
    assert "ok" in handler.get_project_profile({"project_id": "test-proj"})
    assert "ok" in handler.search_project_context({"project_id": "test-proj"})
    assert "ok" in handler.list_memories({"project_id": "test-proj"})


def test_tags_non_string_returns_error(handler):
    r = handler.propose_memory({
        "project_id": "test-proj",
        "title": "test",
        "content": "content",
        "tags": ["ok", 123],
        "actor": "test",
    })
    assert r["ok"] is False
    assert r["error"]["code"] == "invalid_params"


def test_no_traceback_in_error(handler):
    r = handler.approve_memory({"memory_id": "nonexistent"})
    assert r["ok"] is False
    err_text = str(r)
    assert "Traceback" not in err_text
    assert "raise" not in err_text


# ── 11. make_response / make_error_response ──────────────────

def test_make_response():
    r = make_response({"key": "value"})
    assert r == {"ok": True, "data": {"key": "value"}}


def test_make_error_response():
    r = make_error_response("code123", "message", {"detail": "x"})
    assert r["ok"] is False
    assert r["error"]["code"] == "code123"
    assert r["error"]["message"] == "message"
    assert r["error"]["details"] == {"detail": "x"}

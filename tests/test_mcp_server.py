"""MCP server 可测试性 + 配置路径 + 错误码 测试 (Phase 5.1)。"""

import os
import tempfile
from pathlib import Path

import pytest

from project_memory_mcp.app_context import AppContext
from project_memory_mcp.tools.handlers import ToolHandler


# ── helpers ────────────────────────────────────────────────────

def _write_projects_yml(config_dir: Path, extra=""):
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "projects.yml").write_text(f"""\
projects:
  test-proj:
    name: "测试"
    slug: "test-proj"
    status: active
    recognition:
      root_paths: ["/test/proj"]
      aliases: ["test", "测试"]
      tech_stack_keywords: ["python"]
    knowledge_policy:
      auto_approve_threshold: 0.8
    review_policy:
      allow_ai_auto_approve: false
  proj2:
    name: "项目二"
    slug: "proj2"
    status: active
    recognition:
      root_paths: ["/test/proj2"]
      aliases: ["p2"]
defaults:
  knowledge_policy:
    auto_approve_threshold: -1
    max_candidate_per_task: 20
    retention_days: 365
  review_policy:
    allow_ai_auto_approve: false
    forbidden_auto_types: []
    risk_threshold_for_review: medium
    require_review_if_conflict: true{extra}
""", encoding="utf-8")


@pytest.fixture
def ctx():
    tmp = Path(tempfile.mkdtemp())
    config_dir = tmp / "config"
    db_path = tmp / "memory.db"
    _write_projects_yml(config_dir)
    c = AppContext(config_dir=config_dir, db_path=db_path)
    c.sync_projects()
    yield c
    c.db.close()
    import shutil
    shutil.rmtree(str(tmp), ignore_errors=True)


@pytest.fixture
def handler(ctx):
    return ToolHandler(ctx)


# ── 1. server.py 可测试性 ────────────────────────────────────

def test_create_server_with_ctx(tmp_path):
    """create_server(ctx=test_ctx) 能成功注册 9 个工具。"""
    pytest.importorskip("mcp.server.fastmcp")
    from project_memory_mcp.server import create_server

    config_dir = tmp_path / "config"
    db_path = tmp_path / "memory.db"
    _write_projects_yml(config_dir)
    ctx_test = AppContext(config_dir=config_dir, db_path=db_path)
    ctx_test.sync_projects()

    server = create_server(ctx=ctx_test)
    tools = server._tool_manager._tools if hasattr(server, '_tool_manager') else {}
    tool_names = list(tools.keys()) if tools else []

    mvp_tools = [
        "list_projects", "resolve_project", "get_project_profile",
        "search_project_context", "propose_memory", "list_memories",
        "approve_memory", "reject_memory", "deprecate_memory",
    ]
    for name in mvp_tools:
        assert name in tool_names, f"缺少 tool: {name}"


def test_create_server_env_config(tmp_path, monkeypatch):
    """环境变量 PROJECT_MEMORY_CONFIG_DIR / PROJECT_MEMORY_DB_PATH 生效。"""
    from project_memory_mcp.server import _resolve_config_dir, _resolve_db_path

    config_dir = tmp_path / "custom_config"
    config_dir.mkdir()
    (config_dir / "projects.yml").write_text("projects: {}\ndefaults: {}", encoding="utf-8")

    db_path = tmp_path / "custom" / "test.db"

    monkeypatch.setenv("PROJECT_MEMORY_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("PROJECT_MEMORY_DB_PATH", str(db_path))

    resolved_config = _resolve_config_dir()
    resolved_db = _resolve_db_path()

    assert resolved_config == config_dir
    assert resolved_db == db_path


# ── 2. project_id 校验 ────────────────────────────────────────

def test_search_missing_project(handler):
    r = handler.search_project_context({"project_id": "missing-proj", "query": "test"})
    assert r["ok"] is False
    assert r["error"]["code"] == "project_not_found"


def test_list_memories_missing_project(handler):
    r = handler.list_memories({"project_id": "missing-proj"})
    assert r["ok"] is False
    assert r["error"]["code"] == "project_not_found"


# ── 3. resolve 错误码 ────────────────────────────────────────

def test_resolve_nonexistent_project(handler):
    r = handler.resolve_project({"project_id": "missing-proj"})
    assert r["ok"] is False
    assert r["error"]["code"] == "project_not_found"


# ── 4. task_description / related_files ──────────────────────

def test_propose_with_task_description(handler):
    """task_description 含别名可 resolve 到项目。"""
    r = handler.propose_memory({
        "task_description": "修改测试项目的订单模块",
        "title": "测试知识",
        "content": "安全内容",
        "actor": "test",
    })
    assert r["ok"] is True
    assert r["data"]["memory_id"] != ""


def test_search_with_related_files(handler):
    """related_files 路径可 resolve。"""
    r = handler.search_project_context({
        "related_files": ["/test/proj2/main.py"],
        "query": "test",
    })
    # proj2 的 root_path 是 /test/proj2，文件匹配应 resolve 到 proj2
    assert r["ok"] is True
    assert r["data"]["project_id"] == "proj2"


# ── 5. sync_projects 返回值 ─────────────────────────────────

def test_sync_projects_return(ctx):
    n = ctx.sync_projects()
    assert isinstance(n, int)
    assert n >= 2  # 至少两个项目


# ── 6. 错误码区分 ────────────────────────────────────────────

def test_governance_error_memory_not_found(handler):
    r = handler.approve_memory({"memory_id": "nonexistent"})
    assert r["ok"] is False
    assert r["error"]["code"] == "memory_not_found"


def test_governance_error_invalid_state(handler):
    # 先提交一条知识
    pr = handler.propose_memory({
        "project_id": "test-proj",
        "title": "测试",
        "content": "内容",
        "confidence": 0.9,
        "source_type": "user_confirmed",
        "actor": "test",
    })
    mid = pr["data"]["memory_id"]
    # 批准
    handler.approve_memory({"memory_id": mid})
    # 再次批准应报 invalid_state
    r = handler.approve_memory({"memory_id": mid})
    assert r["ok"] is False
    assert r["error"]["code"] == "invalid_state"


# ── Phase 5.2: lazy import + 路径一致性 ──────────────────────

def test_import_without_mcp():
    """没有 mcp 包时，路径解析仍可 import。"""
    from project_memory_mcp.server import _resolve_config_dir, _resolve_db_path
    assert callable(_resolve_config_dir)
    assert callable(_resolve_db_path)


def test_create_server_skip_without_mcp():
    """没有 mcp 包时 create_server 应 skip。"""
    pytest.importorskip("mcp.server.fastmcp")
    from project_memory_mcp.server import create_server
    assert callable(create_server)


def test_config_path_cwd_priority(tmp_path, monkeypatch):
    """cwd/config/projects.yml 存在时，使用 cwd 作为根。"""
    from project_memory_mcp.server import _resolve_project_root

    monkeypatch.setenv("PROJECT_MEMORY_CONFIG_DIR", "")
    monkeypatch.setenv("PROJECT_MEMORY_DB_PATH", "")

    cwd_config = tmp_path / "config"
    cwd_config.mkdir()
    (cwd_config / "projects.yml").write_text("projects: {}\ndefaults: {}", encoding="utf-8")

    monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)

    config_dir, db_path = _resolve_project_root()
    assert config_dir == cwd_config
    assert db_path.parent == tmp_path / "data"


def test_single_env_config_dir_same_root(tmp_path, monkeypatch):
    """只设 PROJECT_MEMORY_CONFIG_DIR 时，db 跟随同一项目根。"""
    from project_memory_mcp.server import _resolve_project_root

    root = tmp_path / "my-proj"
    cfg = root / "config"
    cfg.mkdir(parents=True)
    (cfg / "projects.yml").write_text("projects: {}", encoding="utf-8")

    monkeypatch.setenv("PROJECT_MEMORY_CONFIG_DIR", str(cfg))
    monkeypatch.delenv("PROJECT_MEMORY_DB_PATH", raising=False)

    config_dir, db_path = _resolve_project_root()
    assert config_dir == cfg
    assert db_path == root / "data" / "memory.db"


def test_single_env_db_path_same_root(tmp_path, monkeypatch):
    """只设 PROJECT_MEMORY_DB_PATH 时，config 跟随同一项目根。"""
    from project_memory_mcp.server import _resolve_project_root

    root = tmp_path / "my-proj"
    data_dir = root / "data"
    data_dir.mkdir(parents=True)
    db = data_dir / "test.db"

    monkeypatch.setenv("PROJECT_MEMORY_DB_PATH", str(db))
    monkeypatch.delenv("PROJECT_MEMORY_CONFIG_DIR", raising=False)

    config_dir, db_path = _resolve_project_root()
    assert db_path == db
    assert config_dir == root / "config"


def test_both_env_set_explicit(tmp_path, monkeypatch):
    """两个 env 都设置时，各自使用显式值。"""
    from project_memory_mcp.server import _resolve_project_root

    c = tmp_path / "custom-config"
    c.mkdir()
    (c / "projects.yml").write_text("projects: {}", encoding="utf-8")
    d = tmp_path / "custom" / "my.db"

    monkeypatch.setenv("PROJECT_MEMORY_CONFIG_DIR", str(c))
    monkeypatch.setenv("PROJECT_MEMORY_DB_PATH", str(d))

    config_dir, db_path = _resolve_project_root()
    assert config_dir == c
    assert db_path == d


def test_no_env_no_cwd_fallback_src(monkeypatch):
    """无 env 且 cwd/config 不存在时，fallback 到源码根。"""
    from project_memory_mcp.server import _resolve_project_root, _SRC_ROOT

    monkeypatch.setenv("PROJECT_MEMORY_CONFIG_DIR", "")
    monkeypatch.setenv("PROJECT_MEMORY_DB_PATH", "")

    # 确保 cwd/config 不存在
    if (Path.cwd() / "config" / "projects.yml").exists():
        config_dir, db_path = _resolve_project_root()
        assert config_dir == Path.cwd() / "config"
    else:
        config_dir, db_path = _resolve_project_root()
        assert config_dir == _SRC_ROOT / "config"
        assert db_path == _SRC_ROOT / "data" / "memory.db"


# ── Phase 5.3: resolve_project 精确字段 ──────────────────────

def test_resolve_explicit_id_method(handler):
    r = handler.resolve_project({"project_id": "test-proj"})
    assert r["ok"] is True
    assert r["data"]["match_method"] == "explicit_id"


def test_resolve_workspace_path_method(handler):
    r = handler.resolve_project({"workspace_path": "/test/proj"})
    assert r["ok"] is True
    assert r["data"]["match_method"] == "workspace_path"



# ── Phase 5.2: search 返回字段 ───────────────────────────────

def test_search_returns_full_fields(handler):
    r = handler.search_project_context({"project_id": "test-proj", "query": "test"})
    assert r["ok"] is True
    assert "total_found" in r["data"]
    assert "total_returned" in r["data"]
    assert "search_method" in r["data"]
    assert "fallback_activated" in r["data"]


def test_search_total_returned_matches_context_pack(handler):
    r = handler.search_project_context({"project_id": "test-proj", "query": "test"})
    cp = r["data"]["context_pack"]
    total = (
        len(cp.get("project_context", []))
        + len(cp.get("shared_context", []))
        + len(cp.get("global_context", []))
    )
    assert r["data"]["total_returned"] == total
def test_tags_error_invalid_params(handler):
    r = handler.propose_memory({
        "project_id": "test-proj",
        "title": "test",
        "content": "content",
        "tags": ["ok", 123],
        "actor": "test",
    })
    assert r["ok"] is False
    assert r["error"]["code"] == "invalid_params"

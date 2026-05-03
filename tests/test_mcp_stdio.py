"""
MCP stdio 相关测试 — check_mcp_server / test_mcp_stdio_client 脚本可运行。
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"


def _run(name: str, env: dict, timeout: int = 30):
    return subprocess.run(
        [sys.executable, str(_SCRIPTS_DIR / name)],
        env=env, cwd=str(_PROJECT_ROOT),
        capture_output=True, text=True, timeout=timeout,
    )


def _run_with_args(name: str, args: str, env: dict, timeout: int = 60):
    return subprocess.run(
        [sys.executable, str(_SCRIPTS_DIR / name)] + args.split(),
        env=env, cwd=str(_PROJECT_ROOT),
        capture_output=True, text=True, timeout=timeout,
    )


def _write_config(config_dir: Path):
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


def test_check_mcp_server_runs():
    """check_mcp_server.py 可运行且 exit 0。"""
    pytest.importorskip("mcp")
    tmp = Path(tempfile.mkdtemp())
    try:
        config_dir = tmp / "config"
        db_path = tmp / "data" / "memory.db"
        _write_config(config_dir)
        env = os.environ.copy()
        env["PROJECT_MEMORY_CONFIG_DIR"] = str(config_dir)
        env["PROJECT_MEMORY_DB_PATH"] = str(db_path)
        r = _run("check_mcp_server.py", env)
        assert r.returncode == 0, f"exit={r.returncode}\n{r.stderr}"
        assert "MCP server 创建成功" in r.stdout
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_stdio_client_allow_missing_mcp():
    """--allow-missing-mcp 在 mcp 存在时也应 exit 0。"""
    pytest.importorskip("mcp")
    tmp = Path(tempfile.mkdtemp())
    try:
        config_dir = tmp / "config"
        _write_config(config_dir)
        env = os.environ.copy()
        env["PROJECT_MEMORY_CONFIG_DIR"] = str(config_dir)
        env["PROJECT_MEMORY_DB_PATH"] = str(tmp / "data" / "memory.db")
        r = _run_with_args("test_mcp_stdio_client.py", "--allow-missing-mcp", env, timeout=60)
        assert r.returncode == 0, f"exit={r.returncode}\n{r.stderr}"
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_stdio_client_help():
    """--help 输出包含 --use-current-db 说明。"""
    r = _run_with_args("test_mcp_stdio_client.py", "--help", os.environ.copy())
    assert "use-current-db" in r.stdout.replace("-", "").replace("_", "").lower() \
        or "current" in r.stdout.lower()


def test_create_server_registers_9_tools():
    """create_server(ctx) 注册 9 个 tools。"""
    pytest.importorskip("mcp.server.fastmcp")
    tmp = Path(tempfile.mkdtemp())
    try:
        config_dir = tmp / "config"
        db_path = tmp / "data" / "memory.db"
        _write_config(config_dir)
        os.environ["PROJECT_MEMORY_CONFIG_DIR"] = str(config_dir)
        os.environ["PROJECT_MEMORY_DB_PATH"] = str(db_path)
        from project_memory_mcp.app_context import AppContext
        from project_memory_mcp.server import create_server
        ctx = AppContext(config_dir=config_dir, db_path=db_path)
        server = create_server(ctx=ctx)
        tools = server._tool_manager._tools if hasattr(server, '_tool_manager') else {}
        tool_names = list(tools.keys()) if tools else []
        expected = [
            "list_projects", "resolve_project", "get_project_profile",
            "search_project_context", "propose_memory", "list_memories",
            "approve_memory", "reject_memory", "deprecate_memory",
        ]
        for name in expected:
            assert name in tool_names, f"缺少 tool: {name}"
        ctx.db.close()
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)

"""
MCP server 启动条件检查 — 不进入 stdio loop。

使用：
    python scripts/check_mcp_server.py
    exit 0 = 可以启动, exit 1 = 有阻塞问题
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

_exit_code = 0


def _ok(msg: str):
    print(f"  [OK] {msg}")


def _fail(msg: str):
    global _exit_code
    print(f"  [FAIL] {msg}")
    _exit_code = 1


def main():
    global _exit_code
    print("=" * 50)
    print("  MCP Server 启动条件检查")
    print("=" * 50)

    # 1. mcp 包
    try:
        import mcp  # noqa: F401
        _ok("mcp 包已安装")
    except ImportError:
        _fail("mcp 包未安装，请 pip install mcp")
        sys.exit(1)

    # 2. 路径
    import os
    config_dir = os.environ.get("PROJECT_MEMORY_CONFIG_DIR", str(_PROJECT_ROOT / "config"))
    db_path = os.environ.get("PROJECT_MEMORY_DB_PATH", str(_PROJECT_ROOT / "data" / "memory.db"))
    _ok(f"config_dir = {config_dir}")
    _ok(f"db_path = {db_path}")

    if not Path(config_dir, "projects.yml").exists():
        _fail(f"projects.yml 不存在: {config_dir}")
    else:
        _ok("projects.yml 存在")

    # 3. AppContext
    try:
        from project_memory_mcp.app_context import AppContext
        ctx = AppContext(config_dir=Path(config_dir), db_path=Path(db_path))
        _ok("AppContext 初始化成功")
    except Exception as exc:
        _fail(f"AppContext 初始化失败: {exc}")
        print("\n请先运行: python scripts/init_db.py && python scripts/sync_projects.py")
        sys.exit(1)

    # 4. sync_projects
    try:
        n = ctx.sync_projects()
        _ok(f"sync_projects: {n} 个项目")
    except Exception as exc:
        _fail(f"sync_projects 失败: {exc}")

    # 5. create_server
    try:
        from project_memory_mcp.server import create_server
        server = create_server(ctx=ctx)
        tools = server._tool_manager._tools if hasattr(server, '_tool_manager') else {}
        n_tools = len(tools)
        _ok(f"MCP server 创建成功, tools = {n_tools}")
        if n_tools == 9:
            _ok("9 个 MVP tools 已注册")
        else:
            _fail(f"期望 9 个 tools, 实际 {n_tools}")
    except Exception as exc:
        _fail(f"create_server 失败: {exc}")

    ctx.db.close()

    print(f"\n{'=' * 50}")
    if _exit_code == 0:
        print("  全部检查通过, 可以启动 MCP server")
    else:
        print("  存在阻塞问题, 请修复后重试")
    print(f"{'=' * 50}")
    return _exit_code


if __name__ == "__main__":
    sys.exit(main())

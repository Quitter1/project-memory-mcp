"""
真实 MCP stdio client 测试 — 通过 stdio 启动 server 并调用 tools。

使用：
    python scripts/test_mcp_stdio_client.py
    exit 0 = 测试通过, exit 1 = 失败

如果本机未安装 mcp 或 client API 不可用，输出清晰提示并 exit 0 跳过。
"""

import asyncio
import json
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

_exit_code = 0


def _fail(msg: str):
    global _exit_code
    print(f"  [FAIL] {msg}")
    _exit_code = 1


def _ok(msg: str):
    print(f"  [OK] {msg}")


async def _run_tests():
    global _exit_code
    try:
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from mcp import ClientSession
    except ImportError:
        print("mcp 未安装，跳过 stdio client 测试")
        return

    python = sys.executable
    config_dir = os.environ.get("PROJECT_MEMORY_CONFIG_DIR", str(_PROJECT_ROOT / "config"))
    db_path = os.environ.get("PROJECT_MEMORY_DB_PATH", str(_PROJECT_ROOT / "data" / "memory.db"))

    server_params = StdioServerParameters(
        command=python,
        args=["-m", "project_memory_mcp"],
        env={
            "PROJECT_MEMORY_CONFIG_DIR": config_dir,
            "PROJECT_MEMORY_DB_PATH": db_path,
            "PROJECT_MEMORY_LOG_DIR": os.environ.get("PROJECT_MEMORY_LOG_DIR", str(_PROJECT_ROOT / "logs")),
            "PROJECT_MEMORY_LOG_LEVEL": "INFO",
            "PYTHONIOENCODING": "utf-8",
        },
    )

    print(f"启动 server: {python} -m project_memory_mcp")
    print(f"config_dir = {config_dir}")

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                _ok("session initialized")

                # 1. list tools
                tools_result = await session.list_tools()
                tool_names = [t.name for t in tools_result.tools]
                print(f"  tools = {len(tool_names)}: {tool_names}")
                if len(tool_names) >= 9:
                    _ok(f"{len(tool_names)} 个 tools 已注册")
                else:
                    _fail(f"期望 >=9 个 tools, 实际 {len(tool_names)}")

                # 2. call list_projects
                r = await session.call_tool("list_projects", {"status_filter": "active"})
                result = json.loads(r.content[0].text)
                if result.get("ok"):
                    projects = result.get("data", {}).get("projects", [])
                    _ok(f"list_projects: {len(projects)} 个项目")
                    print(f"    slugs: {[p.get('slug') for p in projects]}")
                else:
                    _fail(f"list_projects 失败: {result}")

                # 3. call search_project_context
                r = await session.call_tool("search_project_context", {
                    "project_id": "biaopai-erp",
                    "query": "产品",
                    "max_results": 5,
                })
                result = json.loads(r.content[0].text)
                if result.get("ok"):
                    cp = result.get("data", {}).get("context_pack", {})
                    n = len(cp.get("project_context", []))
                    print(f"  search: {n} 条结果 (project_context)")
                    _ok("search_project_context 成功")
                else:
                    code = result.get("error", {}).get("code", "unknown")
                    print(f"  search 返回: code={code}")
                    # project_not_found 是可接受的（测试配置可能没有 biaopai-erp）
                    if code in ("project_not_found",):
                        _ok("search_project_context 返回稳定错误码")
                    else:
                        _fail(f"search_project_context 失败: {result}")

                # 4. call propose_memory (普通内容)
                r = await session.call_tool("propose_memory", {
                    "project_id": "biaopai-erp",
                    "title": "MCP stdio 测试知识",
                    "content": "通过 stdio client 提交的测试知识",
                    "actor": "stdio-test",
                })
                result = json.loads(r.content[0].text)
                if result.get("ok"):
                    status = result.get("data", {}).get("status")
                    print(f"  propose status={status}")
                    if status in ("pending_review", "approved", "rejected"):
                        _ok(f"propose_memory status={status}")
                    else:
                        _fail(f"未知状态: {status}")
                else:
                    code = result.get("error", {}).get("code")
                    if code == "project_not_found":
                        _ok("propose_memory project_not_found（可用测试配置）")
                    else:
                        _fail(f"propose_memory 失败: {result}")

                # 5. call propose_memory (blocked)
                r = await session.call_tool("propose_memory", {
                    "project_id": "biaopai-erp",
                    "title": "私钥测试",
                    "content": "-----BEGIN RSA PRIVATE KEY-----\ntest",
                    "actor": "stdio-test",
                })
                result = json.loads(r.content[0].text)
                if result.get("ok"):
                    if result.get("data", {}).get("status") == "rejected":
                        _ok("propose_memory blocked → rejected")
                    else:
                        _fail("blocked 内容未 rejected")
                else:
                    code = result.get("error", {}).get("code", "unknown")
                    if code == "project_not_found":
                        _ok("propose_memory 返回 project_not_found")
                    else:
                        _fail(f"blocked propose 失败: {result}")

    except asyncio.TimeoutError:
        _fail("stdio client 超时")
    except Exception as exc:
        _fail(f"stdio client 异常: {type(exc).__name__}: {exc}")

    print(f"\n{'=' * 50}")
    if _exit_code == 0:
        print("  MCP stdio client 测试全部通过")
    else:
        print("  MCP stdio client 测试存在失败项")
    print(f"{'=' * 50}")


def main():
    try:
        asyncio.run(_run_tests())
    except KeyboardInterrupt:
        print("\n用户中断")
    return _exit_code


if __name__ == "__main__":
    sys.exit(main())

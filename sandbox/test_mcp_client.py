"""
开发调试 MCP 客户端。

用于本地开发时手动测试 MCP tools，不依赖 Claude Code / Codex。

使用方法：
    python sandbox/test_mcp_client.py [tool_name] [json_args]

示例：
    python sandbox/test_mcp_client.py list_projects '{}'
    python sandbox/test_mcp_client.py resolve_project '{"workspace_path": "D:/workspace/biaopai-erp"}'
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main():
    """测试 MCP 工具调用。"""
    # TODO: 阶段 5 实现
    tool_name = sys.argv[1] if len(sys.argv) > 1 else "list_projects"
    args_json = sys.argv[2] if len(sys.argv) > 2 else "{}"
    print(f"调用工具: {tool_name}")
    print(f"参数: {args_json}")
    print("MCP 客户端测试 — 阶段 5 实现")


if __name__ == "__main__":
    main()

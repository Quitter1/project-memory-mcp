"""入口：python -m project_memory_mcp — 启动 MCP stdio server。"""


def main():
    """启动 MCP server。"""
    from .server import main as server_main
    server_main()


if __name__ == "__main__":
    main()

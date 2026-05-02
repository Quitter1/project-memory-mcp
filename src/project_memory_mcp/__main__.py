"""入口：python -m project_memory_mcp"""


def main():
    """启动 MCP server。"""
    from .server import create_and_run_server

    create_and_run_server()


if __name__ == "__main__":
    main()

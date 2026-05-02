"""工具路由 + 参数校验 + 业务分发。"""


class ToolHandler:
    """MCP 工具处理分发器。"""

    def __init__(self, resolver, search_service, governance, memory_repo, project_repo):
        self.resolver = resolver
        self.search_service = search_service
        self.governance = governance
        self.memory_repo = memory_repo
        self.project_repo = project_repo

    # TODO: 阶段 5 实现
    # handle(tool_name: str, params: dict) -> dict

"""
MCP Server — 基于 mcp==1.27.0 FastMCP，不手写 JSON-RPC。

职责：
1. 创建 FastMCP 实例
2. 初始化 AppContext
3. 注册 9 个 MCP tools
4. stdio 启动入口

日志全部写 stderr，stdout 由 MCP SDK 管理。
"""

import sys
import traceback
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .app_context import AppContext
from .tools.handlers import ToolHandler, make_error_response

# 配置目录：项目根/config
_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
# 数据库路径：项目根/data/memory.db
_DB_PATH = Path(__file__).parent.parent.parent / "data" / "memory.db"


def _create_context() -> AppContext:
    """创建并初始化 AppContext。"""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    ctx = AppContext(config_dir=_CONFIG_DIR, db_path=_DB_PATH)
    # 启动时同步 projects.yml → SQLite
    ctx.sync_projects()
    return ctx


def create_server() -> FastMCP:
    """创建 FastMCP 实例并注册所有工具。"""
    mcp = FastMCP("project-memory-mcp")
    ctx = _create_context()
    handler = ToolHandler(ctx)

    # ── 查询类 ──────────────────────────────────────────────

    @mcp.tool()
    async def list_projects(status_filter: str = "active") -> dict:
        """列出已配置项目，返回 name/slug/status/memory_count。"""
        return handler.list_projects({"status_filter": status_filter})

    @mcp.tool()
    async def resolve_project(
        project_id: str = "",
        workspace_path: str = "",
        changed_files: list = None,
        related_files: list = None,
        task_description: str = "",
    ) -> dict:
        """多策略项目识别：支持 project_id/workspace_path/changed_files/task_description。"""
        return handler.resolve_project({
            "project_id": project_id or None,
            "workspace_path": workspace_path or None,
            "changed_files": changed_files,
            "related_files": related_files,
            "task_description": task_description,
        })

    @mcp.tool()
    async def get_project_profile(project_id: str = "") -> dict:
        """获取项目配置 + 知识统计概览。"""
        return handler.get_project_profile({"project_id": project_id})

    # ── 检索 ──────────────────────────────────────────────

    @mcp.tool()
    async def search_project_context(
        project_id: str = "",
        workspace_path: str = "",
        changed_files: list = None,
        query: str = "",
        modules: list = None,
        types: list = None,
        tags: list = None,
        max_results: int = 10,
        min_confidence: float = None,
        include_shared: bool = True,
        include_global: bool = True,
        include_candidates: bool = False,
    ) -> dict:
        """检索项目上下文，返回 context_pack 格式。支持 project_id 自动 resolve。"""
        return handler.search_project_context({
            "project_id": project_id or None,
            "workspace_path": workspace_path or None,
            "changed_files": changed_files,
            "query": query,
            "modules": modules,
            "types": types,
            "tags": tags,
            "max_results": max_results,
            "min_confidence": min_confidence,
            "include_shared": include_shared,
            "include_global": include_global,
            "include_candidates": include_candidates,
        })

    # ── 写入 ──────────────────────────────────────────────

    @mcp.tool()
    async def propose_memory(
        project_id: str = "",
        workspace_path: str = "",
        changed_files: list = None,
        title: str = "",
        content: str = "",
        type: str = "other",
        module: str = "",
        tags: list = None,
        confidence: float = 0.5,
        source_type: str = "ai_inferred",
        source_evidence: dict = None,
        source_file: str = "",
        source_line: int = None,
        scope: str = "project",
        allowed_projects: list = None,
        actor: str = "mcp-agent",
        task_id: str = "",
    ) -> dict:
        """提交候选知识，走完整治理流水线（校验→去重→审批→写入）。"""
        return handler.propose_memory({
            "project_id": project_id or None,
            "workspace_path": workspace_path or None,
            "changed_files": changed_files,
            "title": title,
            "content": content,
            "type": type,
            "module": module,
            "tags": tags,
            "confidence": confidence,
            "source_type": source_type,
            "source_evidence": source_evidence,
            "source_file": source_file,
            "source_line": source_line,
            "scope": scope,
            "allowed_projects": allowed_projects,
            "actor": actor,
            "task_id": task_id,
        })

    # ── 查询 ──────────────────────────────────────────────

    @mcp.tool()
    async def list_memories(
        project_id: str = "",
        status_filter: str = "",
        type: str = "",
        module: str = "",
        tag: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """列出项目知识条目，支持按状态/类型/模块/标签过滤。"""
        return handler.list_memories({
            "project_id": project_id,
            "status_filter": status_filter or None,
            "type": type or None,
            "module": module or None,
            "tag": tag or None,
            "limit": limit,
            "offset": offset,
        })

    # ── 治理 ──────────────────────────────────────────────

    @mcp.tool()
    async def approve_memory(
        memory_id: str = "",
        reviewer: str = "system",
        comment: str = "",
        confidence_override: float = None,
    ) -> dict:
        """审核通过候选/待审核知识，变为 approved。"""
        return handler.approve_memory({
            "memory_id": memory_id,
            "reviewer": reviewer,
            "comment": comment,
            "confidence_override": confidence_override,
        })

    @mcp.tool()
    async def reject_memory(
        memory_id: str = "",
        reviewer: str = "system",
        reason: str = "",
    ) -> dict:
        """审核拒绝候选/待审核知识，变为 rejected（终态）。"""
        return handler.reject_memory({
            "memory_id": memory_id,
            "reviewer": reviewer,
            "reason": reason,
        })

    @mcp.tool()
    async def deprecate_memory(
        memory_id: str = "",
        reason: str = "",
    ) -> dict:
        """废弃已生效知识，变为 deprecated（终态）。"""
        return handler.deprecate_memory({
            "memory_id": memory_id,
            "reason": reason,
        })

    return mcp


def main():
    """stdio 启动入口。"""
    try:
        server = create_server()
        server.run(transport="stdio")
    except Exception:
        tb = traceback.format_exc()
        print(f"[server] {tb}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()

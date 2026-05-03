"""
MCP Server — 基于 mcp==1.27.0 FastMCP，不手写 JSON-RPC。

配置路径解析（优先级）：
  1. 显式设置 PROJECT_MEMORY_CONFIG_DIR / PROJECT_MEMORY_DB_PATH → 分别使用
  2. cwd/config/projects.yml 存在 → config_dir=cwd/config, db_path=cwd/data/memory.db
  3. fallback → 源码根/config, 源码根/data/memory.db

日志全部写 stderr，stdout 由 MCP SDK 管理。
"""

import os
import sys
from pathlib import Path

# 源码相对 fallback 根目录
_SRC_ROOT = Path(__file__).parent.parent.parent


def _resolve_project_root() -> tuple[Path, Path]:
    """
    按优先级解析 config_dir 和 db_path，确保来自同一项目根。

    规则：
    1. 两个 env 都设置 → 分别使用
    2. 只设 PROJECT_MEMORY_CONFIG_DIR → db 跟随 config 所在项目根
    3. 只设 PROJECT_MEMORY_DB_PATH → config 跟随 db 所在项目根
    4. 都没设 → cwd/config 存在则用 cwd，否则源码根 fallback
    """
    env_config = os.environ.get("PROJECT_MEMORY_CONFIG_DIR")
    env_db = os.environ.get("PROJECT_MEMORY_DB_PATH")

    # 两个都设置：分别使用
    if env_config and env_db:
        c = Path(env_config)
        d = Path(env_db)
        d.parent.mkdir(parents=True, exist_ok=True)
        return c, d

    # 只设置 config_dir → 推断 db_path 在同一项目根下
    if env_config:
        c = Path(env_config)
        root = c.parent if c.name == "config" else c
        d = root / "data" / "memory.db"
        d.parent.mkdir(parents=True, exist_ok=True)
        return c, d

    # 只设置 db_path → 推断 config_dir 在同一项目根下
    if env_db:
        d = Path(env_db)
        root = d.parent.parent if d.parent.name == "data" else d.parent
        d.parent.mkdir(parents=True, exist_ok=True)
        return root / "config", d

    # 都没设置：cwd/config/projects.yml 存在则用 cwd
    if (Path.cwd() / "config" / "projects.yml").exists():
        d = Path.cwd() / "data" / "memory.db"
        d.parent.mkdir(parents=True, exist_ok=True)
        return Path.cwd() / "config", d

    # 源码根 fallback
    d = _SRC_ROOT / "data" / "memory.db"
    d.parent.mkdir(parents=True, exist_ok=True)
    return _SRC_ROOT / "config", d


def _resolve_config_dir() -> Path:
    return _resolve_project_root()[0]


def _resolve_db_path() -> Path:
    return _resolve_project_root()[1]


def _create_context():
    """创建并初始化 AppContext。"""
    from .app_context import AppContext

    config_dir, db_path = _resolve_project_root()

    if not (config_dir / "projects.yml").exists():
        msg = f"[server] 找不到 projects.yml，请检查 config_dir: {config_dir}"
        print(msg, file=sys.stderr)
        raise FileNotFoundError(msg)

    ctx = AppContext(config_dir=config_dir, db_path=db_path)
    ctx.sync_projects()
    return ctx


def create_server(ctx=None):
    """
    创建 FastMCP 实例并注册 9 个 tools。

    ctx=None 时自动创建 AppContext。
    测试时可传入已有 ctx。
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "未安装 mcp 包，请先 pip install -e '.[dev]' 或 pip install mcp"
        ) from exc

    if ctx is None:
        ctx = _create_context()

    mcp = FastMCP("project-memory-mcp")
    # import handler lazily to avoid circular deps at module level
    from .tools.handlers import ToolHandler
    handler = ToolHandler(ctx)

    # ── 查询类 ──────────────────────────────────────────────

    @mcp.tool()
    async def list_projects(status_filter: str = "active") -> dict:
        return handler.list_projects({"status_filter": status_filter})

    @mcp.tool()
    async def resolve_project(
        project_id: str = "",
        workspace_path: str = "",
        changed_files: list = None,
        related_files: list = None,
        task_description: str = "",
    ) -> dict:
        return handler.resolve_project({
            "project_id": project_id or None,
            "workspace_path": workspace_path or None,
            "changed_files": changed_files,
            "related_files": related_files,
            "task_description": task_description,
        })

    @mcp.tool()
    async def get_project_profile(project_id: str = "") -> dict:
        return handler.get_project_profile({"project_id": project_id})

    # ── 检索 ──────────────────────────────────────────────

    @mcp.tool()
    async def search_project_context(
        project_id: str = "",
        workspace_path: str = "",
        changed_files: list = None,
        related_files: list = None,
        task_description: str = "",
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
        return handler.search_project_context({
            "project_id": project_id or None,
            "workspace_path": workspace_path or None,
            "changed_files": changed_files,
            "related_files": related_files,
            "task_description": task_description,
            "query": query, "modules": modules, "types": types, "tags": tags,
            "max_results": max_results, "min_confidence": min_confidence,
            "include_shared": include_shared, "include_global": include_global,
            "include_candidates": include_candidates,
        })

    # ── 写入 ──────────────────────────────────────────────

    @mcp.tool()
    async def propose_memory(
        project_id: str = "",
        workspace_path: str = "",
        changed_files: list = None,
        related_files: list = None,
        task_description: str = "",
        title: str = "", content: str = "", type: str = "other",
        module: str = "", tags: list = None, confidence: float = 0.5,
        source_type: str = "ai_inferred", source_evidence: dict = None,
        source_file: str = "", source_line: int = None,
        scope: str = "project", allowed_projects: list = None,
        actor: str = "mcp-agent", task_id: str = "",
    ) -> dict:
        return handler.propose_memory({
            "project_id": project_id or None,
            "workspace_path": workspace_path or None,
            "changed_files": changed_files,
            "related_files": related_files,
            "task_description": task_description,
            "title": title, "content": content, "type": type,
            "module": module, "tags": tags, "confidence": confidence,
            "source_type": source_type, "source_evidence": source_evidence,
            "source_file": source_file, "source_line": source_line,
            "scope": scope, "allowed_projects": allowed_projects,
            "actor": actor, "task_id": task_id,
        })

    # ── 查询 ──────────────────────────────────────────────

    @mcp.tool()
    async def list_memories(
        project_id: str = "", status_filter: str = "",
        type: str = "", module: str = "", tag: str = "",
        limit: int = 50, offset: int = 0,
    ) -> dict:
        return handler.list_memories({
            "project_id": project_id,
            "status_filter": status_filter or None,
            "type": type or None, "module": module or None,
            "tag": tag or None, "limit": limit, "offset": offset,
        })

    # ── 治理 ──────────────────────────────────────────────

    @mcp.tool()
    async def approve_memory(
        memory_id: str = "", reviewer: str = "system",
        comment: str = "", confidence_override: float = None,
    ) -> dict:
        return handler.approve_memory({
            "memory_id": memory_id, "reviewer": reviewer,
            "comment": comment, "confidence_override": confidence_override,
        })

    @mcp.tool()
    async def reject_memory(
        memory_id: str = "", reviewer: str = "system", reason: str = "",
    ) -> dict:
        return handler.reject_memory({
            "memory_id": memory_id, "reviewer": reviewer, "reason": reason,
        })

    @mcp.tool()
    async def deprecate_memory(memory_id: str = "", reason: str = "") -> dict:
        return handler.deprecate_memory({
            "memory_id": memory_id, "reason": reason,
        })

    return mcp


def main():
    try:
        server = create_server()
        server.run(transport="stdio")
    except Exception as exc:
        import logging
        import sys as _sys
        logging.getLogger("project_memory_mcp").critical(
            "server_fatal exc_type=%s", type(exc).__name__,
        )
        _sys.exit(1)


if __name__ == "__main__":
    main()

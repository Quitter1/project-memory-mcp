"""工具路由 + 参数校验 + 统一错误处理 + resolve helper。"""

import traceback
import sys
from typing import Optional

from ..project.resolver import ResolveRequest


# ── 统一返回格式 ──────────────────────────────────────────────

def make_response(data: dict) -> dict:
    return {"ok": True, "data": data}


def make_error_response(code: str, message: str, details: dict | None = None) -> dict:
    return {
        "ok": False,
        "error": {"code": code, "message": message, "details": details or {}},
    }


# ── resolve helper ──────────────────────────────────────────────

def raw_resolve(ctx, params: dict) -> tuple:
    """返回 (ProjectConfig | None, info_dict, error_response | None)。
    info_dict 包含 match_method, confidence, warning 等真实字段。"""
    project_id = params.get("project_id")
    workspace_path = params.get("workspace_path")
    changed_files = params.get("changed_files")
    related_files = params.get("related_files")
    task_description = params.get("task_description")

    try:
        req = ResolveRequest(
            project_id=project_id,
            workspace_path=workspace_path,
            changed_files=changed_files or [],
            related_files=related_files or [],
            task_description=task_description or "",
        )
        result = ctx.resolver.resolve(req)

        if result.resolved and not result.ambiguous:
            pid = result.project.get("id", "") if result.project else ""
            cfg = ctx.config_loader.get_project(pid)
            if cfg is not None:
                info = {
                    "match_method": result.match_method or "unknown",
                    "confidence": result.confidence or 0.5,
                }
                if result.project and result.project.get("warning"):
                    info["warning"] = result.project["warning"]
                return cfg, info, None

            return None, {}, make_error_response(
                "project_not_found",
                f"项目 {pid} 不在配置中",
                {"suggest_projects": [p.slug for p in ctx.config_loader.list_active_projects()]},
            )

        if result.ambiguous:
            return None, {}, make_error_response(
                "ambiguous_project",
                "多个项目匹配，请显式指定 project_id",
                {"candidates": result.candidates},
            )

        if result.error and "project_not_found" in result.error:
            return None, {}, make_error_response(
                "project_not_found",
                f"项目 {project_id} 不存在",
                {"suggest_projects": [p.slug for p in ctx.config_loader.list_active_projects()]},
            )

        return None, {}, make_error_response(
            "project_id_required",
            "无法识别项目，请提供 project_id、workspace_path 或 changed_files",
            {"suggest_projects": [p.slug for p in ctx.config_loader.list_active_projects()]},
        )
    except Exception as exc:
        tb = traceback.format_exc()
        print(f"[raw_resolve] {tb}", file=sys.stderr)
        return None, {}, make_error_response("resolve_error", str(exc))


def resolve_project_or_error(ctx, **kwargs):
    """返回 (ProjectConfig | None, error | None)。兼容旧接口。"""
    cfg, info, error = raw_resolve(ctx, kwargs)
    return cfg, error


# ── ToolHandler ─────────────────────────────────────────────────

class ToolHandler:
    """MCP 工具处理分发器，委托到各 tools/*.py 的 handle() 函数。"""

    def __init__(self, ctx):
        self.ctx = ctx

    def list_projects(self, params: dict) -> dict:
        from .list_projects import handle
        return handle(self.ctx, params)

    def resolve_project(self, params: dict) -> dict:
        from .resolve_project import handle
        return handle(self.ctx, params)

    def get_project_profile(self, params: dict) -> dict:
        from .get_project_profile import handle
        return handle(self.ctx, params)

    def search_project_context(self, params: dict) -> dict:
        from .search_context import handle
        return handle(self.ctx, params)

    def propose_memory(self, params: dict) -> dict:
        from .propose_memory import handle
        return handle(self.ctx, params)

    def list_memories(self, params: dict) -> dict:
        from .list_memories import handle
        return handle(self.ctx, params)

    def approve_memory(self, params: dict) -> dict:
        from .approve_memory import handle
        return handle(self.ctx, params)

    def reject_memory(self, params: dict) -> dict:
        from .reject_memory import handle
        return handle(self.ctx, params)

    def deprecate_memory(self, params: dict) -> dict:
        from .deprecate_memory import handle
        return handle(self.ctx, params)

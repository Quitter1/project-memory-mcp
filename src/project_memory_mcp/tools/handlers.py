"""工具路由 + 参数校验 + 统一错误处理 + resolve helper。

Phase 6.3: 所有响应包含 request_id，tool 调用写入日志。
"""

import time
import traceback
import sys
import logging
from typing import Optional

from ..project.resolver import ResolveRequest
from ..utils.logging import new_request_id

logger = logging.getLogger("project_memory_mcp")


# ── 统一返回格式 ──────────────────────────────────────────────

def make_response(data: dict, request_id: str = "") -> dict:
    result = {"ok": True, "request_id": request_id, "data": data} if request_id else {"ok": True, "data": data}
    return result


def make_error_response(code: str, message: str, details: dict | None = None, request_id: str = "") -> dict:
    error = {"code": code, "message": message, "details": details or {}}
    result = {"ok": False, "request_id": request_id, "error": error} if request_id else {"ok": False, "error": error}
    return result


def _safe_param_summary(params: dict) -> str:
    """生成安全的参数摘要 — 只输出长度/计数/安全标识，不含原文。"""
    parts = []
    for key in ("project_id", "type", "module", "scope", "source_type", "status_filter"):
        if key in params and params[key]:
            parts.append(f"{key}={str(params[key])[:40]}")
    if params.get("query"):
        parts.append(f"query_length={len(str(params['query']))}")
    if params.get("title"):
        parts.append(f"title_length={len(str(params['title']))}")
    if params.get("content"):
        parts.append(f"content_length={len(str(params['content']))}")
    if params.get("tags"):
        parts.append(f"tag_count={len(params['tags'])}")
    if params.get("changed_files"):
        cf = params["changed_files"]
        parts.append(f"changed_files_count={len(cf) if cf else 0}")
    if params.get("related_files"):
        rf = params["related_files"]
        parts.append(f"related_files_count={len(rf) if rf else 0}")
    if params.get("modules"):
        parts.append(f"modules_count={len(params['modules'])}")
    if params.get("types"):
        parts.append(f"types_count={len(params['types'])}")
    if params.get("source_evidence"):
        parts.append("source_evidence_present=1")
    return ", ".join(parts)


def _log_tool_start(tool: str, request_id: str, params: dict):
    summary = _safe_param_summary(params)
    logger.info("tool_start request_id=%s tool=%s %s", request_id, tool, summary)


def _log_tool_success(tool: str, request_id: str, duration_ms: float, extra: str = ""):
    logger.info("tool_success request_id=%s tool=%s duration_ms=%.1f %s",
                request_id, tool, duration_ms, extra)


def _log_tool_error(tool: str, request_id: str, code: str, duration_ms: float):
    logger.warning("tool_error request_id=%s tool=%s code=%s duration_ms=%.1f",
                   request_id, tool, code, duration_ms)


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
    """MCP 工具处理分发器，委托到各 tools/*.py 的 handle() 函数。

    Phase 6.3: 自动注入 request_id 到所有响应，记录工具调用日志。
    """

    def __init__(self, ctx):
        self.ctx = ctx

    def _dispatch(self, tool: str, module_name: str, params: dict) -> dict:
        request_id = new_request_id()
        _log_tool_start(tool, request_id, params)
        t0 = time.monotonic()

        try:
            import importlib
            mod = importlib.import_module(f".{module_name}", "project_memory_mcp.tools")
            result = mod.handle(self.ctx, params)
        except Exception as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            logger.error("tool_exception request_id=%s tool=%s exc=%s", request_id, tool, exc)
            _log_tool_error(tool, request_id, "internal_error", duration_ms)
            return make_error_response("internal_error", str(exc), request_id=request_id)

        duration_ms = (time.monotonic() - t0) * 1000

        # 注入 request_id
        if result.get("ok"):
            result["request_id"] = request_id
            _log_tool_success(tool, request_id, duration_ms)
        else:
            result["request_id"] = request_id
            code = result.get("error", {}).get("code", "unknown")
            _log_tool_error(tool, request_id, code, duration_ms)

        # 搜索诊断日志
        if tool == "search_project_context" and result.get("ok"):
            d = result.get("data", {})
            cp = d.get("context_pack", {})
            extra = (
                f"total_found={d.get('total_found', 0)} "
                f"total_returned={d.get('total_returned', 0)} "
                f"project_count={len(cp.get('project_context', []))} "
                f"shared_count={len(cp.get('shared_context', []))} "
                f"global_count={len(cp.get('global_context', []))} "
            )
            logger.info("search_summary request_id=%s %s", request_id, extra.strip())

        # 治理决策日志
        if tool == "propose_memory" and result.get("ok"):
            d = result.get("data", {})
            decision = "approved" if d.get("review_decision", {}).get("auto_approved") else "pending_review"
            if d.get("status") == "rejected":
                decision = "rejected"
            logger.info(
                "governance_decision request_id=%s project_id=%s source_type=%s "
                "scope=%s risk_level=%s decision=%s status=%s",
                request_id,
                params.get("project_id", "?"),
                params.get("source_type", "?"),
                params.get("scope", "?"),
                d.get("risk_level", "?"),
                decision,
                d.get("status", "?"),
            )

        return result

    def list_projects(self, params: dict) -> dict:
        return self._dispatch("list_projects", "list_projects", params)

    def resolve_project(self, params: dict) -> dict:
        return self._dispatch("resolve_project", "resolve_project", params)

    def get_project_profile(self, params: dict) -> dict:
        return self._dispatch("get_project_profile", "get_project_profile", params)

    def search_project_context(self, params: dict) -> dict:
        return self._dispatch("search_project_context", "search_context", params)

    def propose_memory(self, params: dict) -> dict:
        return self._dispatch("propose_memory", "propose_memory", params)

    def list_memories(self, params: dict) -> dict:
        return self._dispatch("list_memories", "list_memories", params)

    def approve_memory(self, params: dict) -> dict:
        return self._dispatch("approve_memory", "approve_memory", params)

    def reject_memory(self, params: dict) -> dict:
        return self._dispatch("reject_memory", "reject_memory", params)

    def deprecate_memory(self, params: dict) -> dict:
        return self._dispatch("deprecate_memory", "deprecate_memory", params)

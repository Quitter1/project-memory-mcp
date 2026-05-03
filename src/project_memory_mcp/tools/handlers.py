"""工具路由 + 参数校验 + 统一错误处理。

Phase 5 实现：
- make_response / make_error_response 统一返回格式
- resolve_project_or_error 统一 project_id resolve 逻辑
- ToolHandler 分发器（所有 tool handler 共享同一个 AppContext）
"""

import traceback
import sys
from typing import Optional

from ..project.resolver import ResolveRequest
from ..config.schema import ProjectConfig


# ── 统一返回格式 ──────────────────────────────────────────────

def make_response(data: dict) -> dict:
    return {"ok": True, "data": data}


def make_error_response(code: str, message: str, details: dict | None = None) -> dict:
    return {
        "ok": False,
        "error": {"code": code, "message": message, "details": details or {}},
    }


# ── resolve helper ──────────────────────────────────────────────

def resolve_project_or_error(ctx, project_id=None, workspace_path=None,
                             changed_files=None, related_files=None,
                             task_description=None):
    """统一的 project resolve 逻辑。返回 (ProjectConfig | None, error | None)。"""
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
                return cfg, None
            return None, make_error_response("project_not_found", f"项目 {pid} 不在配置中")

        if result.ambiguous:
            return None, make_error_response(
                "ambiguous_project",
                "多个项目匹配，请显式指定 project_id",
                {"candidates": result.candidates},
            )

        return None, make_error_response(
            "project_id_required",
            "无法识别项目，请提供 project_id、workspace_path 或 changed_files",
            {
                "suggest_projects": [
                    p.slug for p in ctx.config_loader.list_active_projects()
                ],
            },
        )
    except Exception as exc:
        tb = traceback.format_exc()
        print(f"[resolve_project_or_error] {tb}", file=sys.stderr)
        return None, make_error_response("resolve_error", str(exc))


# ── ToolHandler ─────────────────────────────────────────────────

class ToolHandler:
    """MCP 工具处理分发器。"""

    def __init__(self, ctx):
        self.ctx = ctx

    # ── 查询类 ──────────────────────────────────────────────────

    def list_projects(self, params: dict) -> dict:
        status_filter = params.get("status_filter", "active")
        if status_filter == "active":
            projects = self.ctx.config_loader.list_active_projects()
        else:
            projects = self.ctx.config_loader.load_all_projects()
            if status_filter:
                projects = [p for p in projects if p.status == status_filter]

        project_list = []
        for p in projects:
            profile = self.ctx.profile_builder.build(p.id)
            stats = profile.get("stats", {}) if profile else {}
            project_list.append({
                "id": p.id,
                "name": p.name,
                "slug": p.slug,
                "status": p.status,
                "memory_count": stats.get("total_memories", 0),
            })
        return make_response({"projects": project_list, "total": len(project_list)})

    def resolve_project(self, params: dict) -> dict:
        project, error = resolve_project_or_error(
            self.ctx,
            project_id=params.get("project_id"),
            workspace_path=params.get("workspace_path"),
            changed_files=params.get("changed_files"),
            related_files=params.get("related_files"),
            task_description=params.get("task_description"),
        )
        if error:
            return error

        return make_response({
            "resolved": True,
            "ambiguous": False,
            "project": {
                "id": project.id,
                "name": project.name,
                "slug": project.slug,
                "status": project.status,
            },
            "match_method": params.get("project_id") and "explicit" or "inferred",
            "confidence": 0.95 if params.get("project_id") else 0.5,
            "warnings": [],
        })

    def get_project_profile(self, params: dict) -> dict:
        pid = params.get("project_id", "")
        if not pid:
            return make_error_response("invalid_params", "project_id 是必填参数")

        profile = self.ctx.profile_builder.build(pid)
        if profile is None:
            return make_error_response("project_not_found", f"项目 {pid} 不存在")

        project_data = profile.get("project", {})
        stats_data = profile.get("stats", {})
        return make_response({
            "project": project_data,
            "stats": stats_data,
        })

    # ── 检索 ────────────────────────────────────────────────────

    def search_project_context(self, params: dict) -> dict:
        project_id = params.get("project_id")
        workspace_path = params.get("workspace_path")
        changed_files = params.get("changed_files")

        if not project_id and (workspace_path or changed_files):
            project, error = resolve_project_or_error(
                self.ctx,
                workspace_path=workspace_path,
                changed_files=changed_files,
            )
            if error:
                return error
            project_id = project.id

        if not project_id:
            return make_error_response(
                "project_id_required",
                "请提供 project_id、workspace_path 或 changed_files",
            )

        try:
            result_set = self.ctx.search_service.search(
                project_id=project_id,
                query=params.get("query", ""),
                modules=params.get("modules") or None,
                types=params.get("types") or None,
                tags=params.get("tags") or None,
                max_results=params.get("max_results", 10),
                min_confidence=params.get("min_confidence"),
                include_shared=params.get("include_shared", True),
                include_global=params.get("include_global", True),
                include_candidates=params.get("include_candidates", False),
            )
            return make_response({
                "query": params.get("query", ""),
                "project_id": project_id,
                "context_pack": result_set.context_pack,
                "total_found": result_set.total_found,
            })
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[search_project_context] {tb}", file=sys.stderr)
            return make_error_response("search_error", str(exc))

    # ── 写入 ────────────────────────────────────────────────────

    def propose_memory(self, params: dict) -> dict:
        project_id = params.get("project_id")
        workspace_path = params.get("workspace_path")
        changed_files = params.get("changed_files")

        if not project_id and (workspace_path or changed_files):
            project, error = resolve_project_or_error(
                self.ctx,
                workspace_path=workspace_path,
                changed_files=changed_files,
            )
            if error:
                return error
            project_id = project.id

        if not project_id:
            return make_error_response(
                "project_id_required",
                "请提供 project_id、workspace_path 或 changed_files",
            )

        project_cfg = self.ctx.config_loader.get_project(project_id)
        if project_cfg is None:
            return make_error_response("project_not_found", f"项目 {project_id} 不存在")

        try:
            result = self.ctx.governance.propose_memory(
                title=params.get("title", ""),
                content=params.get("content", ""),
                project=project_cfg,
                knowledge_type=params.get("type", "other"),
                module=params.get("module", ""),
                tags=params.get("tags"),
                confidence=params.get("confidence", 0.5),
                source_type=params.get("source_type", "ai_inferred"),
                source_evidence=params.get("source_evidence"),
                source_file=params.get("source_file"),
                source_line=params.get("source_line"),
                scope=params.get("scope", "project"),
                allowed_projects=params.get("allowed_projects"),
                actor=params.get("actor", "mcp-agent"),
                task_id=params.get("task_id"),
            )
            return make_response(result)
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[propose_memory] {tb}", file=sys.stderr)
            return make_error_response("propose_error", str(exc))

    def list_memories(self, params: dict) -> dict:
        project_id = params.get("project_id", "")
        if not project_id:
            return make_error_response("invalid_params", "project_id 是必填参数")

        status_filter = params.get("status_filter")
        if status_filter and isinstance(status_filter, str):
            status_filter = [s.strip() for s in status_filter.split(",") if s.strip()]

        items = self.ctx.memory_repo.list_memories(
            project_id=project_id,
            status_filter=status_filter or None,
            type_filter=params.get("type") or None,
            module_filter=params.get("module") or None,
            tag_filter=params.get("tag") or None,
            limit=min(params.get("limit", 50), 100),
            offset=params.get("offset", 0),
        )
        return make_response({
            "memories": [
                {
                    "id": m.id,
                    "title": m.title,
                    "type": m.type,
                    "module": m.module,
                    "status": m.status,
                    "index_status": m.index_status,
                    "risk_level": m.risk_level,
                    "confidence": m.confidence,
                    "scope": m.scope,
                    "tags": m.tags,
                    "created_at": m.created_at,
                    "updated_at": m.updated_at,
                }
                for m in items
            ],
            "total": len(items),
        })

    # ── 治理 ────────────────────────────────────────────────────

    def approve_memory(self, params: dict) -> dict:
        memory_id = params.get("memory_id", "")
        if not memory_id:
            return make_error_response("invalid_params", "memory_id 是必填参数")

        try:
            result = self.ctx.governance.approve_memory(
                memory_id=memory_id,
                reviewer=params.get("reviewer", "system"),
                comment=params.get("comment", ""),
                confidence_override=params.get("confidence_override"),
            )
            return make_response(result)
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[approve_memory] {tb}", file=sys.stderr)
            return make_error_response("approve_error", str(exc))

    def reject_memory(self, params: dict) -> dict:
        memory_id = params.get("memory_id", "")
        if not memory_id:
            return make_error_response("invalid_params", "memory_id 是必填参数")

        try:
            result = self.ctx.governance.reject_memory(
                memory_id=memory_id,
                reviewer=params.get("reviewer", "system"),
                reason=params.get("reason", ""),
            )
            return make_response(result)
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[reject_memory] {tb}", file=sys.stderr)
            return make_error_response("reject_error", str(exc))

    def deprecate_memory(self, params: dict) -> dict:
        memory_id = params.get("memory_id", "")
        if not memory_id:
            return make_error_response("invalid_params", "memory_id 是必填参数")

        try:
            result = self.ctx.governance.deprecate_memory(
                memory_id=memory_id,
                reason=params.get("reason", ""),
                actor=params.get("actor", "mcp-agent"),
            )
            return make_response(result)
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[deprecate_memory] {tb}", file=sys.stderr)
            return make_error_response("deprecate_error", str(exc))

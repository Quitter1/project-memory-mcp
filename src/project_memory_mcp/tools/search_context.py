"""search_project_context — 检索项目上下文，返回 context_pack。"""

from .handlers import make_response, make_error_response, resolve_project_or_error


def handle(ctx, params: dict) -> dict:
    project_id = params.get("project_id")
    workspace_path = params.get("workspace_path")
    changed_files = params.get("changed_files")

    if not project_id and (workspace_path or changed_files or params.get("related_files") or params.get("task_description")):
        project, error = resolve_project_or_error(
            ctx,
            workspace_path=workspace_path,
            changed_files=changed_files,
            related_files=params.get("related_files"),
            task_description=params.get("task_description"),
        )
        if error:
            return error
        project_id = project.id

    if not project_id:
        return make_error_response("project_id_required", "请提供 project_id、workspace_path 或 changed_files")

    if ctx.config_loader.get_project(project_id) is None:
        return make_error_response("project_not_found", f"项目 {project_id} 不存在")

    try:
        result_set = ctx.search_service.search(
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
            "project_resolved": True,
            "context_pack": result_set.context_pack,
            "total_found": result_set.total_found,
            "total_returned": getattr(result_set, "total_returned", 0),
            "search_method": getattr(result_set, "search_method", "keyword"),
            "fallback_activated": getattr(result_set, "fallback_activated", False),
        })
    except Exception as exc:
        import logging
        logging.getLogger("project_memory_mcp").error(
            "search_context_exception exc_type=%s", type(exc).__name__,
        )
        return make_error_response("internal_error", "工具执行失败，请查看日志")

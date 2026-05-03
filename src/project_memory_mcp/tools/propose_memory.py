"""propose_memory — 提交候选知识，走完整治理流水线。"""

from .handlers import make_response, make_error_response, resolve_project_or_error

STABLE_MESSAGES = {
    "invalid_params": "参数错误",
    "internal_error": "工具执行失败，请查看日志",
}


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

    project_cfg = ctx.config_loader.get_project(project_id)
    if project_cfg is None:
        return make_error_response("project_not_found", f"项目 {project_id} 不存在")

    try:
        result = ctx.governance.propose_memory(
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
        import logging
        name = type(exc).__name__
        if "GovernanceError" in name or "tags" in str(exc).lower():
            logging.getLogger("project_memory_mcp").warning(
                "propose_memory_error exc_type=%s", name,
            )
            return make_error_response("invalid_params", STABLE_MESSAGES.get("invalid_params", "参数错误"))
        logging.getLogger("project_memory_mcp").error(
            "propose_memory_exception exc_type=%s", name,
        )
        return make_error_response("internal_error", STABLE_MESSAGES.get("internal_error", "工具执行失败"))

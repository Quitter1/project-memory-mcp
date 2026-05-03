"""list_memories — 列出项目知识条目。"""

from .handlers import make_response, make_error_response


def handle(ctx, params: dict) -> dict:
    project_id = params.get("project_id", "")
    if not project_id:
        return make_error_response("invalid_params", "project_id 是必填参数")

    if ctx.config_loader.get_project(project_id) is None:
        return make_error_response("project_not_found", f"项目 {project_id} 不存在")

    status_filter = params.get("status_filter")
    if status_filter and isinstance(status_filter, str):
        status_filter = [s.strip() for s in status_filter.split(",") if s.strip()]

    items = ctx.memory_repo.list_memories(
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
                "id": m.id, "title": m.title, "type": m.type,
                "module": m.module, "status": m.status,
                "index_status": m.index_status, "risk_level": m.risk_level,
                "confidence": m.confidence, "scope": m.scope,
                "tags": m.tags, "created_at": m.created_at,
                "updated_at": m.updated_at,
            }
            for m in items
        ],
        "total": len(items),
    })

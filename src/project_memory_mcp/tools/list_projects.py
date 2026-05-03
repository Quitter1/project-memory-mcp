"""list_projects — 列出可用项目。"""

from .handlers import make_response


def handle(ctx, params: dict) -> dict:
    status_filter = params.get("status_filter", "active")
    loader = ctx.config_loader
    if status_filter == "active":
        projects = loader.list_active_projects()
    else:
        projects = loader.load_all_projects()
        if status_filter:
            projects = [p for p in projects if p.status == status_filter]

    project_list = []
    for p in projects:
        profile = ctx.profile_builder.build(p.id)
        stats = profile.get("stats", {}) if profile else {}
        project_list.append({
            "id": p.id, "name": p.name, "slug": p.slug,
            "status": p.status, "memory_count": stats.get("total_memories", 0),
        })
    return make_response({"projects": project_list, "total": len(project_list)})

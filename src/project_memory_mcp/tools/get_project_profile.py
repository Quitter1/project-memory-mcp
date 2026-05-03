"""get_project_profile — 项目配置 + 知识统计。"""

from .handlers import make_response, make_error_response


def handle(ctx, params: dict) -> dict:
    pid = params.get("project_id", "")
    if not pid:
        return make_error_response("invalid_params", "project_id 是必填参数")

    profile = ctx.profile_builder.build(pid)
    if profile is None:
        return make_error_response("project_not_found", f"项目 {pid} 不存在")

    return make_response({
        "project": profile.get("project", {}),
        "stats": profile.get("stats", {}),
    })

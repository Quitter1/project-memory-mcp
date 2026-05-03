"""resolve_project — 多策略项目识别。"""

from .handlers import make_response, resolve_project_or_error, raw_resolve


def handle(ctx, params: dict) -> dict:
    project, info, error = raw_resolve(ctx, params)
    if error:
        return error

    result = {
        "resolved": True,
        "ambiguous": False,
        "project": {
            "id": project.id, "name": project.name,
            "slug": project.slug, "status": project.status,
        },
        "match_method": info.get("match_method", "unknown"),
        "confidence": info.get("confidence", 0.5),
    }

    if info.get("warning"):
        result["warnings"] = [info["warning"]]

    return make_response(result)

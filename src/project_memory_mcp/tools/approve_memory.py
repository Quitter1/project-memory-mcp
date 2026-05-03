"""approve_memory — 审核通过候选知识。"""

from .handlers import make_response, make_error_response


def handle(ctx, params: dict) -> dict:
    memory_id = params.get("memory_id", "")
    if not memory_id:
        return make_error_response("invalid_params", "memory_id 是必填参数")

    try:
        result = ctx.governance.approve_memory(
            memory_id=memory_id,
            reviewer=params.get("reviewer", "system"),
            comment=params.get("comment", ""),
            confidence_override=params.get("confidence_override"),
        )
        return make_response(result)
    except Exception as exc:
        from ..utils.logging import redact_sensitive
        import logging
        name = type(exc).__name__
        if "GovernanceError" in name:
            code = "memory_not_found" if "不存在" in str(exc) else "invalid_state"
            logging.getLogger("project_memory_mcp").warning(
                "approve_memory_error exc_type=%s code=%s", name, code,
            )
            return make_error_response(code, redact_sensitive(str(exc)))
        logging.getLogger("project_memory_mcp").error(
            "approve_memory_exception exc_type=%s", name,
        )
        return make_error_response("internal_error", "工具执行失败，请查看日志")

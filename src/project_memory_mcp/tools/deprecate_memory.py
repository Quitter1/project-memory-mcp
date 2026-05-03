"""deprecate_memory — 废弃已生效知识。"""

import traceback
import sys
from .handlers import make_response, make_error_response


def handle(ctx, params: dict) -> dict:
    memory_id = params.get("memory_id", "")
    if not memory_id:
        return make_error_response("invalid_params", "memory_id 是必填参数")

    try:
        result = ctx.governance.deprecate_memory(
            memory_id=memory_id,
            reason=params.get("reason", ""),
            actor=params.get("actor", "mcp-agent"),
        )
        return make_response(result)
    except Exception as exc:
        name = type(exc).__name__
        if "GovernanceError" in name:
            code = "memory_not_found" if "不存在" in str(exc) else "invalid_state"
            print(f"[deprecate_memory] {name}: {exc}", file=sys.stderr)
            return make_error_response(code, str(exc))
        tb = traceback.format_exc()
        print(f"[deprecate_memory] {tb}", file=sys.stderr)
        return make_error_response("governance_error", str(exc))

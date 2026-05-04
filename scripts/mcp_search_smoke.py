"""
MCP 搜索冒烟测试 — 通过 ToolHandler 调用 search_project_context。

使用：
    python scripts/mcp_search_smoke.py --project rpa-electron --query "商品图上传" --repeat 3
"""

import argparse
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--repeat", type=int, default=2)
    args = p.parse_args()

    import _paths
    _ = _paths.ensure_import_paths()
    from project_memory_mcp.app_context import AppContext
    from project_memory_mcp.tools.handlers import ToolHandler

    config_dir, db_path = _paths.get_project_paths()

    for run in range(args.repeat):
        ctx = AppContext(config_dir=config_dir, db_path=db_path)
        try:
            handler = ToolHandler(ctx)
            t0 = time.monotonic()
            r = handler.search_project_context({
                "project_id": args.project,
                "query": args.query,
            })
            elapsed_ms = (time.monotonic() - t0) * 1000
            if r.get("ok"):
                d = r["data"]
                print(f"run={run + 1} ok=true method={d.get('search_method')}"
                      f" fallback={d.get('fallback_activated')} reason={d.get('fallback_reason','-')}"
                      f" kw={d.get('keyword_count',0)} vec={d.get('vector_count',0)}"
                      f" hyb={d.get('hybrid_count',0)} elapsed_ms={elapsed_ms:.0f}")
            else:
                print(f"run={run + 1} ok=false code={r.get('error',{}).get('code')} elapsed_ms={elapsed_ms:.0f}")
        finally:
            ctx.db.close()


if __name__ == "__main__":
    raise SystemExit(main() or 0)

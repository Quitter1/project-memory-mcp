"""
搜索上下文演示 — 直接调用 KnowledgeSearchService，输出完整 metadata。

使用：
    python scripts/search_context_demo.py --project rpa-electron --query "商品图上传"
"""

import argparse
import json
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
    p.add_argument("--repeat", type=int, default=1)
    args = p.parse_args()

    import _paths
    _ = _paths.ensure_import_paths()
    from project_memory_mcp.app_context import AppContext

    config_dir, db_path = _paths.get_project_paths()

    for run in range(args.repeat):
        ctx = AppContext(config_dir=config_dir, db_path=db_path)
        try:
            t0 = time.monotonic()
            result = ctx.search_service.search(
                project_id=args.project, query=args.query, max_results=10,
            )
            elapsed_ms = (time.monotonic() - t0) * 1000

            print(f"run={run + 1} method={result.search_method} fallback={result.fallback_activated}"
                  f" reason={result.fallback_reason or '-'}"
                  f" kw={result.keyword_count} vec={result.vector_count} hyb={result.hybrid_count}"
                  f" total={result.total_found} elapsed_ms={elapsed_ms:.0f}")

            for item in result.context_pack.get("project_context", []):
                score = item.get("relevance_score", 0)
                print(f"  [{item.get('match_type','')}] score={score:.6f} | {item.get('title','')}")
        finally:
            ctx.db.close()


if __name__ == "__main__":
    raise SystemExit(main() or 0)

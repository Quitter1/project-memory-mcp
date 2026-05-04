"""
Keyword search 演示 — 复现首次慢/第二次快的差异。

使用：
    python scripts/keyword_search_demo.py --project rpa-electron --query "商品图上传到页面"
    python scripts/keyword_search_demo.py --project rpa-electron --query "商品图上传到页面" --repeat 3
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
    from project_memory_mcp.retrieval.keyword_search import KeywordSearchService

    for run in range(args.repeat):
        import sqlite3
        conn = sqlite3.connect(str(_PROJECT_ROOT / "data" / "memory.db"))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")

        t0 = time.monotonic()
        kws = KeywordSearchService(conn)
        results = kws.search(
            project_id=args.project, query=args.query, max_results=10,
            include_shared=False, include_global=False,
        )
        elapsed = (time.monotonic() - t0) * 1000
        print(f"run={run + 1} keyword_count={len(results)} elapsed_ms={elapsed:.0f}")
        if results:
            for r in results[:3]:
                print(f"  [{r.id[:8]}] score={r.relevance_score:.6f} | {r.title[:50]}")

        conn.close()


if __name__ == "__main__":
    raise SystemExit(main() or 0)

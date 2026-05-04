"""
检索评测脚本 — 对比 keyword/vector/hybrid 命中效果。

使用：
    python scripts/eval_search.py
    python scripts/eval_search.py --mode keyword
    python scripts/eval_search.py --case rpa_image_upload_semantic
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
    p.add_argument("--mode", default="hybrid", choices=["keyword", "vector", "hybrid"])
    p.add_argument("--project")
    p.add_argument("--case", help="仅测指定 case_id")
    args = p.parse_args()

    import yaml
    import _paths
    _ = _paths.ensure_import_paths()
    from project_memory_mcp.app_context import AppContext
    from project_memory_mcp.retrieval.keyword_search import KeywordSearchService

    # 加载 cases
    cases_file = _PROJECT_ROOT / "eval" / "search_cases.yml"
    if not cases_file.exists():
        print(f"评测集不存在: {cases_file}")
        return 2
    raw = yaml.safe_load(cases_file.read_text(encoding="utf-8"))
    cases = raw.get("cases", [])

    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
    if args.project:
        cases = [c for c in cases if c.get("project_id") == args.project]

    config_dir, db_path = _paths.get_project_paths()
    ctx = AppContext(config_dir=config_dir, db_path=db_path)

    hit_count = 0
    top1_count = 0
    total_elapsed = 0.0
    failures = 0
    exit_code = 0

    try:
        for case in cases:
            pid = case["project_id"]
            q = case["query"]
            expected = set(case.get("expected_titles", []))
            expected_top1 = case.get("expected_top1", "")
            mode = args.mode if args.mode != case.get("mode", "hybrid") else case.get("mode", "hybrid")

            # 临时设置 mode
            orig_mode = ctx.search_service.mode
            ctx.search_service.mode = mode

            t0 = time.monotonic()
            result = ctx.search_service.search(project_id=pid, query=q, max_results=5)
            elapsed = (time.monotonic() - t0) * 1000
            total_elapsed += elapsed
            ctx.search_service.mode = orig_mode

            titles = [x.get("title", "") for x in result.context_pack.get("project_context", [])]
            hits = [t for t in titles if t in expected]
            hit = bool(hits)
            top1 = titles[0] if titles else ""

            hit_count += int(hit)
            top1_ok = top1 == expected_top1 if expected_top1 else True
            if top1_ok:
                top1_count += 1

            print(f"\ncase_id: {case['id']}")
            print(f"  query_len: {len(q)}")
            print(f"  mode: {mode}")
            print(f"  top1: {top1[:60] if top1 else '(none)'}")
            if expected_top1:
                print(f"  expected_top1: {expected_top1[:60]}")
            print(f"  hit_expected: {'yes' if hit else 'no'}")
            print(f"  top1_ok: {'yes' if top1_ok else 'no'}")
            print(f"  elapsed_ms: {elapsed:.0f}")

            if not hit:
                failures += 1
                print(f"  expected titles not found: {list(expected)}")

    finally:
        ctx.db.close()

    n = len(cases)
    print(f"\n{'=' * 50}")
    print(f"total_cases={n}")
    print(f"hit_rate={hit_count}/{n}")
    print(f"top1_rate={top1_count}/{n}")
    if n > 0:
        print(f"avg_elapsed_ms={total_elapsed / n:.0f}")
    print(f"{'=' * 50}")

    if failures > 0:
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

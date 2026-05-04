"""
向量搜索演示 — keyword vs vector vs hybrid 对比。

使用：
    python scripts/vector_search_demo.py --project rpa-electron --query "商品图上传"
"""

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))


def _print_section(title: str, results: list, method: str):
    print(f"\n{'─' * 60}")
    print(f"  [{method}] {title}: {len(results)} 条")
    print(f"{'─' * 60}")
    for r in results[:10]:
        title_short = (r.get("title", "") or "")[:50]
        score = r.get("relevance_score", r.get("score", 0))
        mid = (r.get("id", "") or "")[:8]
        print(f"  [{mid}] score={score:.6f} | {title_short}")


def _load_title(ctx, memory_id):
    """从 SQLite 读取真实 title。"""
    try:
        m = ctx.memory_repo.get_by_id(memory_id)
        return m.title if m else ""
    except Exception:
        return ""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--query", required=True)
    args = p.parse_args()

    import _paths
    _ = _paths.ensure_import_paths()
    from project_memory_mcp.app_context import AppContext

    config_dir, db_path = _paths.get_project_paths()
    ctx = AppContext(config_dir=config_dir, db_path=db_path)

    try:
        # 1. Keyword search (pure keyword, no vector)
        from project_memory_mcp.retrieval.keyword_search import KeywordSearchService
        kws = KeywordSearchService(ctx.conn)
        kw_items = kws.search(
            project_id=args.project, query=args.query,
            max_results=10, include_shared=False, include_global=False,
        )
        kw_results = []
        for item in kw_items:
            kw_results.append({
                "id": item.id, "title": item.title,
                "relevance_score": item.relevance_score, "source": "keyword",
            })
        _print_section(args.query, kw_results, "keyword")

        # 2. Vector (if enabled)
        if ctx.vector_store is None or ctx.embedder is None:
            print("\n[INFO] Qdrant/embedding 未启用")
            print("请在 config/server.yml 设置 qdrant.enabled=true, embedding.enabled=true")
            return

        try:
            vec = ctx.embedder.embed_text(args.query)
            vector_hits = ctx.vector_store.search(
                vec, args.project, scope_filter="project", top_k=10,
            )
        except Exception as exc:
            print(f"\n[INFO] Vector search 失败: {exc}")
            return

        # 读取 min_vector_score
        min_vs = ctx.search_service.min_vector_score if hasattr(ctx, 'search_service') else 0.001
        print(f"\n  min_vector_score={min_vs}")

        vector_results = []
        for hit in vector_hits:
            if hit["score"] < min_vs:
                continue
            mid = hit["id"]
            title = _load_title(ctx, mid)
            vector_results.append({
                "id": mid, "title": title, "score": hit["score"],
                "relevance_score": hit["score"], "source": "vector",
            })
        _print_section(args.query, vector_results, "vector")

        # 3. Hybrid merge
        hybrid_map = {}
        for r in kw_results:
            mid = r["id"]
            kw_norm = min(r["relevance_score"] / 60.0, 1.0)
            hybrid_map[mid] = {"keyword_score": kw_norm, "vector_score": 0.0, "title": r["title"]}
        for r in vector_results:
            mid = r["id"]
            if mid in hybrid_map:
                hybrid_map[mid]["vector_score"] = r["score"]
            else:
                hybrid_map[mid] = {"keyword_score": 0.0, "vector_score": r["score"], "title": r["title"]}

        hybrid_results = []
        for mid, scores in hybrid_map.items():
            hs = 0.55 * scores["keyword_score"] + 0.45 * scores["vector_score"]
            hybrid_results.append({
                "id": mid, "title": scores["title"], "relevance_score": hs, "source": "hybrid",
            })
        hybrid_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        _print_section(args.query, hybrid_results, "hybrid")

    finally:
        ctx.db.close()


if __name__ == "__main__":
    raise SystemExit(main() or 0)

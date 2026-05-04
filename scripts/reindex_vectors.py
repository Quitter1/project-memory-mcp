"""
向量索引重建 — 将所有 approved 知识同步到 Qdrant。

使用：
    python scripts/reindex_vectors.py --dry-run
    python scripts/reindex_vectors.py --yes
    python scripts/reindex_vectors.py --project rpa-electron --yes
"""

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))


def main():
    p = argparse.ArgumentParser(description="向量索引重建")
    p.add_argument("--dry-run", action="store_true", default=True, help="预览模式")
    p.add_argument("--yes", action="store_true", help="确认执行")
    p.add_argument("--project", help="只处理指定项目")
    args = p.parse_args()

    import _paths
    _ = _paths.ensure_import_paths()
    from project_memory_mcp.app_context import AppContext

    config_dir, db_path = _paths.get_project_paths()
    ctx = AppContext(config_dir=config_dir, db_path=db_path)

    try:
        if ctx.vector_indexer is None:
            print("向量索引未启用 (qdrant.enabled=false 或 embedding 不可用)")
            return

        ctx.vector_store.ensure_collection()

        if args.yes:
            result = ctx.vector_indexer.reindex_all(project_id=args.project, dry_run=False)
        else:
            # 只用 memory_repo 统计
            if args.project:
                items = ctx.memory_repo.list_memories(project_id=args.project, limit=10000)
            else:
                all_projects = ctx.config_loader.list_active_projects()
                items = []
                for prj in all_projects:
                    items.extend(ctx.memory_repo.list_memories(project_id=prj.id, limit=10000))
            approved = [m for m in items if m.status == "approved"]
            result = {"eligible": len(approved), "indexed": 0, "failed": 0, "skipped": 0}

        print(f"eligible: {result['eligible']}")
        if not args.yes:
            print(f"[Dry-run] 使用 --yes 将重建 {result['eligible']} 条向量索引")
        else:
            print(f"indexed: {result['indexed']}, failed: {result['failed']}")

    finally:
        ctx.db.close()


if __name__ == "__main__":
    main()

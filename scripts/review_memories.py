"""
人工审核脚本 — list/show/approve/reject/deprecate 知识。

使用：
    python scripts/review_memories.py list --status pending_review
    python scripts/review_memories.py show --id <memory_id>
    python scripts/review_memories.py approve --id <id> --comment "确认" --yes
    python scripts/review_memories.py reject --id <id> --reason "测试" --yes
    python scripts/review_memories.py deprecate --id <id> --reason "过期" --yes

环境变量: PROJECT_MEMORY_CONFIG_DIR / PROJECT_MEMORY_DB_PATH
"""

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

import _paths  # noqa: E402
_ = _paths.ensure_import_paths()


def main():
    p = argparse.ArgumentParser(description="知识审核")
    sub = p.add_subparsers(dest="cmd")

    # list
    sp_list = sub.add_parser("list")
    sp_list.add_argument("--project")
    sp_list.add_argument("--status", default="pending_review")
    sp_list.add_argument("--type")
    sp_list.add_argument("--module")
    sp_list.add_argument("--tag")
    sp_list.add_argument("--limit", type=int, default=50)

    # show
    sp_show = sub.add_parser("show")
    sp_show.add_argument("--id", required=True)
    sp_show.add_argument("--full", action="store_true", help="显示完整内容")

    # approve/reject/deprecate
    for cmd_name in ("approve", "reject", "deprecate"):
        sp = sub.add_parser(cmd_name)
        sp.add_argument("--id", required=True)
        if cmd_name == "approve":
            sp.add_argument("--comment", default="")
        else:
            sp.add_argument("--reason", default="")
        sp.add_argument("--yes", action="store_true", help="确认执行")

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        return

    from project_memory_mcp.app_context import AppContext
    config_dir, db_path = _paths.get_project_paths()
    ctx = AppContext(config_dir=config_dir, db_path=db_path)

    try:
        if args.cmd == "list":
            pid = args.project
            status_filter = [s.strip() for s in args.status.split(",")] if args.status else None
            items = ctx.memory_repo.list_memories(
                project_id=pid or "", status_filter=status_filter,
                type_filter=args.type, module_filter=args.module,
                tag_filter=args.tag, limit=args.limit,
            ) if pid else []
            if not pid:
                all_projects = ctx.config_loader.list_active_projects()
                items = []
                for prj in all_projects:
                    items.extend(ctx.memory_repo.list_memories(
                        project_id=prj.id, status_filter=status_filter,
                        type_filter=args.type, module_filter=args.module,
                        tag_filter=args.tag, limit=args.limit,
                    ))

            print(f"{'─' * 90}")
            filter_desc = []
            if args.status: filter_desc.append(f"status={args.status}")
            if args.module: filter_desc.append(f"module={args.module}")
            if args.tag: filter_desc.append(f"tag={args.tag}")
            print(f"  {', '.join(filter_desc) or '全部'}  共 {len(items)} 条")
            print(f"{'─' * 90}")
            for m in items:
                title_short = m.title[:45] + ("..." if len(m.title) > 45 else "")
                tags_str = ",".join(m.tags[:3]) if m.tags else "-"
                print(f"  [{m.id[:8]}] {m.project_id} | {m.status} | {m.type} | "
                      f"{m.module or '-'} | conf={m.confidence:.1f} | {m.risk_level} | "
                      f"{title_short}")
                print(f"    tags={tags_str}  created={m.created_at}")
            ctx.db.close()
            return

        elif args.cmd == "show":
            item = ctx.memory_repo.get_by_id(args.id)
            if item is None:
                print(f"知识不存在: {args.id}")
                ctx.db.close()
                sys.exit(1)
            print(f"  id: {item.id}")
            print(f"  project_id: {item.project_id}")
            print(f"  title: {item.title}")
            content = item.content if args.full else item.content[:200] + ("..." if len(item.content) > 200 else "")
            print(f"  content: {content}")
            print(f"  status: {item.status}")
            print(f"  type: {item.type}")
            print(f"  module: {item.module}")
            print(f"  scope: {item.scope}")
            print(f"  confidence: {item.confidence}")
            print(f"  risk_level: {item.risk_level}")
            print(f"  source_type: {item.source_type}")
            print(f"  tags: {item.tags}")
            print(f"  created_at: {item.created_at}")
            print(f"  updated_at: {item.updated_at}")
            ctx.db.close()
            return

        elif args.cmd == "approve":
            item = ctx.memory_repo.get_by_id(args.id)
            if item is None:
                print(f"知识不存在: {args.id}")
                sys.exit(1)
            if not args.yes:
                print(f"[DRY RUN] 将 approve: {item.id[:8]} - {item.title[:50]}")
                print(f"  当前状态: {item.status}")
                print(f"  请加 --yes 确认执行")
                return
            result = ctx.governance.approve_memory(args.id, comment=args.comment)
            print(f"已 approve: {result['memory_id'][:8]} → {result['status']}")
            return

        elif args.cmd == "reject":
            item = ctx.memory_repo.get_by_id(args.id)
            if item is None:
                print(f"知识不存在: {args.id}")
                sys.exit(1)
            if not args.yes:
                print(f"[DRY RUN] 将 reject: {item.id[:8]} - {item.title[:50]}")
                print(f"  当前状态: {item.status}")
                print(f"  请加 --yes 确认执行")
                return
            result = ctx.governance.reject_memory(args.id, reason=args.reason)
            print(f"已 reject: {result['memory_id'][:8]} → {result['status']}")
            return

        elif args.cmd == "deprecate":
            item = ctx.memory_repo.get_by_id(args.id)
            if item is None:
                print(f"知识不存在: {args.id}")
                sys.exit(1)
            if not args.yes:
                print(f"[DRY RUN] 将 deprecate: {item.id[:8]} - {item.title[:50]}")
                print(f"  当前状态: {item.status}")
                print(f"  请加 --yes 确认执行")
                return
            result = ctx.governance.deprecate_memory(args.id, reason=args.reason)
            print(f"已 deprecate: {result['memory_id'][:8]} → {result['status']}")
            return

    finally:
        ctx.db.close()


if __name__ == "__main__":
    main()

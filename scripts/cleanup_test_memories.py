"""
测试知识清理 — 识别并管理 [CC_TEST]/[STDIO_TEST] 测试知识。

使用：
    python scripts/cleanup_test_memories.py --dry-run
    python scripts/cleanup_test_memories.py --reject --yes
    python scripts/cleanup_test_memories.py --include-terminal
    python scripts/cleanup_test_memories.py --project rpa-electron --reject --yes

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

TERMINAL_STATUSES = {"rejected", "deprecated", "superseded"}


def _is_test(item) -> bool:
    title = item.title or ""
    tags = item.tags or []
    if title.startswith("[CC_TEST]") or title.startswith("[STDIO_TEST]"):
        return True
    if "CC_TEST" in tags or "STDIO_TEST" in tags:
        return True
    if item.type == "test" and item.module == "mcp":
        return True
    return False


def main():
    p = argparse.ArgumentParser(description="清理测试知识")
    p.add_argument("--dry-run", action="store_true", default=True, help="预览模式（默认）")
    p.add_argument("--reject", action="store_true", help="拒绝测试知识")
    p.add_argument("--include-approved", action="store_true", help="显示 approved 测试知识")
    p.add_argument("--include-terminal", action="store_true", help="显示 rejected/deprecated/superseded 测试知识")
    p.add_argument("--project", help="只清理指定项目")
    p.add_argument("--yes", action="store_true", help="确认执行")
    args = p.parse_args()

    from project_memory_mcp.app_context import AppContext
    config_dir, db_path = _paths.get_project_paths()
    ctx = AppContext(config_dir=config_dir, db_path=db_path)

    try:
        projects = [args.project] if args.project else [p.id for p in ctx.config_loader.list_active_projects()]
        all_test_items = []

        for pid in projects:
            items = ctx.memory_repo.list_memories(project_id=pid, limit=500)
            for item in items:
                if _is_test(item):
                    all_test_items.append(item)

        if not all_test_items:
            print("没有发现测试知识")
            return

        # 三组分类
        actionable = [m for m in all_test_items if m.status in ("candidate", "pending_review")]
        skipped_terminal = [m for m in all_test_items if m.status in TERMINAL_STATUSES]
        skipped_approved = [m for m in all_test_items if m.status == "approved"]

        print(f"发现测试知识 {len(all_test_items)} 条")
        print(f"  可处理 (candidate/pending_review): {len(actionable)} 条")
        if skipped_terminal:
            print(f"  已跳过 rejected/deprecated/superseded: {len(skipped_terminal)} 条"
                  f" (使用 --include-terminal 显示)")
        else:
            print(f"  已跳过 rejected/deprecated/superseded: 0 条")
        if skipped_approved:
            print(f"  已跳过 approved: {len(skipped_approved)} 条"
                  f" (使用 --include-approved 显示)")
        else:
            print(f"  已跳过 approved: 0 条")

        # 显示列表
        show_items = list(actionable)
        if args.include_terminal:
            show_items.extend(skipped_terminal)
        if args.include_approved:
            show_items.extend(skipped_approved)

        if show_items:
            print()
            for item in show_items:
                marker = "  " if item in actionable else " (跳过) "
                print(f"  [{marker}][{item.status}] {item.project_id} | {item.title[:60]}")

        if not actionable:
            print("\n没有可处理的 candidate/pending_review 测试知识。")
            print("这些 rejected/deprecated 测试知识已不参与检索，通常无需处理。")
            return

        if args.reject and args.yes:
            rejected = 0
            for item in actionable:
                try:
                    ctx.governance.reject_memory(item.id, reason="测试知识清理")
                    rejected += 1
                    print(f"  已 reject: {item.id[:8]}")
                except Exception as exc:
                    print(f"  跳过 {item.id[:8]}: {exc}")
            print(f"处理完成: {rejected}/{len(actionable)}")
        else:
            print(f"\n[Dry-run] 使用 --reject --yes 将拒绝 {len(actionable)} 条测试知识"
                  f" (仅 candidate/pending_review)")

    finally:
        ctx.db.close()


if __name__ == "__main__":
    main()

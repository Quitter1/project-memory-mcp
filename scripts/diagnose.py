"""
诊断脚本 — 检查项目记忆服务运行状态。

使用：
    python scripts/diagnose.py
    python scripts/diagnose.py --project biaopai-erp
    python scripts/diagnose.py --recent-errors

环境变量：
    PROJECT_MEMORY_CONFIG_DIR / PROJECT_MEMORY_DB_PATH
"""

import json
import sys

import _paths
_ = _paths.ensure_import_paths()

from project_memory_mcp.app_context import AppContext


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Project Memory MCP 诊断")
    parser.add_argument("--project", help="指定项目 ID")
    parser.add_argument("--recent-errors", action="store_true", help="显示最近错误")
    args = parser.parse_args()

    config_dir, db_path = _paths.get_project_paths()

    print("=" * 50)
    print("  Project Memory MCP — 运行诊断")
    print("=" * 50)

    # 1. 文件检查
    print("\n[1] 文件检查")
    yml = config_dir / "projects.yml"
    print(f"  projects.yml: {'存在' if yml.exists() else '缺失'} ({yml})")
    print(f"  memory.db: {'存在' if db_path.exists() else '缺失'} ({db_path})")

    log_dir = _paths._PROJECT_ROOT / "logs"
    main_log = log_dir / "project-memory-mcp.log"
    err_log = log_dir / "errors.log"
    print(f"  日志目录: {log_dir} {'(存在)' if log_dir.is_dir() else '(不存在)'}")
    if log_dir.is_dir():
        for name in ["project-memory-mcp.log", "errors.log"]:
            p = log_dir / name
            if p.exists():
                print(f"    {name}: {p.stat().st_size} bytes")

    # 2. 数据库
    print("\n[2] 数据库")
    try:
        ctx = AppContext(config_dir=config_dir, db_path=db_path)
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        uv = conn.execute("PRAGMA user_version").fetchone()[0]
        jm = conn.execute("PRAGMA journal_mode").fetchone()[0]
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        print(f"  user_version={uv}  journal_mode={jm}  foreign_keys={fk}")

        n_p = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        n_m = conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
        n_a = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        print(f"  projects={n_p}  memory_items={n_m}  audit_log={n_a}")

        # 按状态分布
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM memory_items GROUP BY status"
        ).fetchall()
        for r in rows:
            print(f"    {r['status']}: {r['cnt']}")

        # 3. 指定项目详情
        if args.project:
            print(f"\n[3] 项目: {args.project}")
            cfg = ctx.config_loader.get_project(args.project)
            if cfg:
                print(f"  名称: {cfg.name}")
                print(f"  状态: {cfg.status}")
                profile = ctx.profile_builder.build(args.project)
                if profile:
                    stats = profile.get("stats", {})
                    print(f"  总知识: {stats.get('total_memories', 0)}")
            else:
                print(f"  项目不存在")

        # 4. 最近错误
        if args.recent_errors:
            print("\n[4] 最近 audit_log (操作记录)")
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
            for r in rows:
                nv = r["new_value"]
                if nv and len(str(nv)) > 100:
                    nv = str(nv)[:100] + "..."
                print(f"  [{r['created_at']}] {r['action']} | {nv}")

        conn.close()
        ctx.db.close()
    except Exception as exc:
        print(f"  数据库错误: {exc}")

    print(f"\n{'=' * 50}")
    print("  诊断完成")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()

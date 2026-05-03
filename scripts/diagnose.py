"""
诊断脚本 — 检查项目记忆服务运行状态。

使用：
    python scripts/diagnose.py
    python scripts/diagnose.py --project biaopai-erp
    python scripts/diagnose.py --recent-errors
    python scripts/diagnose.py --recent-audit

环境变量：
    PROJECT_MEMORY_CONFIG_DIR / PROJECT_MEMORY_DB_PATH / PROJECT_MEMORY_LOG_DIR
"""

import argparse
import os
import sys

import _paths
_ = _paths.ensure_import_paths()


def _get_log_dir(config_dir):
    """获取日志目录（与 AppContext 逻辑一致）。"""
    env = os.environ.get("PROJECT_MEMORY_LOG_DIR")
    if env:
        return _paths.Path(env)
    return config_dir.parent / "logs"


def _check_db(db_path, config_dir):
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    ok = True
    uv = conn.execute("PRAGMA user_version").fetchone()[0]
    jm = conn.execute("PRAGMA journal_mode").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    print(f"  user_version={uv}")
    print(f"  journal_mode={jm}")
    print(f"  foreign_keys={fk}")

    if fk != 1:
        print("  [FAIL] foreign_keys != 1")
        ok = False
    if jm != "wal":
        print("  [FAIL] journal_mode != wal")
        ok = False
    if uv < 2:
        print(f"  [FAIL] user_version={uv} < 2")
        ok = False

    n_p = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    n_m = conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
    n_a = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    print(f"  projects={n_p}  memory_items={n_m}  audit_log={n_a}")

    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM memory_items GROUP BY status"
    ).fetchall()
    for r in rows:
        print(f"    {r['status']}: {r['cnt']}")

    conn.close()
    return ok


def main():
    parser = argparse.ArgumentParser(description="Project Memory MCP 诊断")
    parser.add_argument("--project", help="指定项目 ID")
    parser.add_argument("--recent-errors", action="store_true", help="显示 errors.log 最后 50 行")
    parser.add_argument("--recent-audit", action="store_true", help="显示最近 20 条 audit_log")
    args = parser.parse_args()

    config_dir, db_path = _paths.get_project_paths()
    log_dir = _get_log_dir(config_dir)

    print("=" * 50)
    print("  Project Memory MCP — 运行诊断")
    print("=" * 50)

    # 1. 文件
    print("\n[1] 文件检查")
    yml = config_dir / "projects.yml"
    print(f"  projects.yml: {'存在' if yml.exists() else '缺失'} ({yml})")
    print(f"  memory.db: {'存在' if db_path.exists() else '缺失'} ({db_path})")
    print(f"  日志目录: {log_dir} {'(存在)' if log_dir.is_dir() else '(不存在)'}")
    if log_dir.is_dir():
        for name in ["project-memory-mcp.log", "errors.log"]:
            p = log_dir / name
            if p.exists():
                print(f"    {name}: {p.stat().st_size} bytes")

    # 2. 数据库
    print("\n[2] 数据库")
    if db_path.exists():
        _check_db(db_path, config_dir)
    else:
        print("  数据库不存在，跳过")

    # 3. 项目详情
    if args.project:
        print(f"\n[3] 项目: {args.project}")
        try:
            from project_memory_mcp.app_context import AppContext
            ctx = AppContext(config_dir=config_dir, db_path=db_path)
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
            ctx.db.close()
        except Exception as exc:
            print(f"  错误: {exc}")

    # 4. errors.log
    if args.recent_errors:
        print(f"\n[4] errors.log 最近行")
        err_file = log_dir / "errors.log"
        if err_file.exists():
            lines = err_file.read_text(encoding="utf-8", errors="replace").strip().split("\n")
            for line in lines[-50:]:
                # 脱敏
                from project_memory_mcp.utils.logging import redact_sensitive
                print(f"  {redact_sensitive(line)[:200]}")
        else:
            print("  errors.log 不存在")

    # 5. audit_log
    if args.recent_audit:
        print(f"\n[5] 最近 audit_log")
        if db_path.exists():
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            rows = conn.execute(
                "SELECT action, project_id, memory_id, reason, created_at "
                "FROM audit_log ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
            for r in rows:
                reason = (r["reason"] or "")[:120]
                print(f"  [{r['created_at']}] {r['action']} "
                      f"project={r['project_id']} reason={reason}")
            conn.close()
        else:
            print("  数据库不存在")

    print(f"\n{'=' * 50}")
    print("  诊断完成")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()

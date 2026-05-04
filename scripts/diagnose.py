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
    """获取日志目录（与 AppContext._init_logging 逻辑一致）。"""
    env = os.environ.get("PROJECT_MEMORY_LOG_DIR")
    if env:
        return _paths.Path(env)

    server_yml = config_dir / "server.yml"
    if server_yml.exists():
        try:
            import yaml
            raw = yaml.safe_load(server_yml.read_text(encoding="utf-8"))
            log_dir = raw.get("logging", {}).get("log_dir") if raw else None
            if log_dir:
                return config_dir.parent / log_dir
        except Exception:
            pass

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
    parser.add_argument("--review-summary", action="store_true", help="显示待审核/测试知识统计")
    parser.add_argument("--vector-summary", action="store_true", help="显示向量索引状态")
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

    # 7. vector-summary
    if args.vector_summary:
        print(f"\n[7] 向量索引摘要")
        try:
            import yaml
            server_yml = config_dir / "server.yml"
            raw = yaml.safe_load(server_yml.read_text(encoding="utf-8")) if server_yml.exists() else {}
            qdrant_cfg = raw.get("qdrant", {}) if raw else {}
            embed_cfg = raw.get("embedding", {}) if raw else {}

            qdrant_enabled = qdrant_cfg.get("enabled", False)
            print(f"  qdrant.enabled = {qdrant_enabled}")
            print(f"  embedding.provider = {embed_cfg.get('provider', 'hashing')}")
            print(f"  embedding.dim = {embed_cfg.get('dim', 512)}")
            print(f"  collection = {qdrant_cfg.get('collection', 'project_memory_items')}")

            # Qdrant reachable?
            if qdrant_enabled and db_path.exists():
                try:
                    from qdrant_client import QdrantClient
                    client = QdrantClient(
                        host=qdrant_cfg.get("host", "127.0.0.1"),
                        port=qdrant_cfg.get("http_port", 6333),
                        timeout=3,
                    )
                    coll_name = qdrant_cfg.get("collection", "project_memory_items")
                    colls = [c.name for c in client.get_collections().collections]
                    if coll_name in colls:
                        info = client.get_collection(coll_name)
                        cnt = info.points_count if hasattr(info, 'points_count') else '?'
                        print(f"  qdrant reachable = yes, points = {cnt}")
                    else:
                        print(f"  qdrant reachable = yes, collection 未创建")
                except Exception:
                    print("  qdrant reachable = no")

            # SQLite counts
            if db_path.exists():
                import sqlite3
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                approved = conn.execute(
                    "SELECT COUNT(*) FROM memory_items WHERE status='approved'"
                ).fetchone()[0]
                indexed_n = conn.execute(
                    "SELECT COUNT(*) FROM memory_items WHERE status='approved' AND index_status='indexed'"
                ).fetchone()[0]
                failed_n = conn.execute(
                    "SELECT COUNT(*) FROM memory_items WHERE index_status='index_failed'"
                ).fetchone()[0]
                not_indexed = approved - indexed_n
                print(f"  approved memories = {approved}")
                print(f"  indexed (index_status) = {indexed_n}")
                print(f"  index_failed = {failed_n}")
                print(f"  not_indexed approved = {not_indexed}")
                conn.close()
        except Exception as exc:
            print(f"  向量摘要获取失败: {exc}")

    # 6. review-summary
    if args.review_summary:
        print(f"\n[6] 审核摘要")
        if db_path.exists():
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")

            rows = conn.execute(
                "SELECT project_id, COUNT(*) as cnt FROM memory_items "
                "WHERE status='pending_review' GROUP BY project_id"
            ).fetchall()
            print("  待审核知识:")
            for r in rows:
                print(f"    {r['project_id']}: {r['cnt']}")
            if not rows:
                print("    (无)")

            rows = conn.execute(
                "SELECT mi.status, COUNT(*) as cnt FROM memory_items mi "
                "WHERE mi.title LIKE '[CC_TEST]%' OR mi.title LIKE '[STDIO_TEST]%' "
                "OR (mi.type = 'test' AND mi.module = 'mcp') "
                "OR EXISTS (SELECT 1 FROM memory_tags mt WHERE mt.memory_id = mi.id "
                "AND mt.tag IN ('CC_TEST', 'STDIO_TEST')) "
                "GROUP BY mi.status"
            ).fetchall()
            print("  测试知识:")
            for r in rows:
                print(f"    {r['status']}: {r['cnt']}")
            if not rows:
                print("    (无)")

            for s in ("rejected", "deprecated"):
                cnt = conn.execute("SELECT COUNT(*) FROM memory_items WHERE status=?", (s,)).fetchone()[0]
                print(f"  {s}: {cnt}")

            cnt = conn.execute("SELECT COUNT(*) FROM audit_log WHERE action='blocked'").fetchone()[0]
            print(f"  blocked: {cnt}")
            cnt = conn.execute("SELECT COUNT(*) FROM audit_log WHERE action='duplicate_rejected'").fetchone()[0]
            print(f"  duplicate_rejected: {cnt}")
            conn.close()

    print(f"\n{'=' * 50}")
    print("  诊断完成")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()

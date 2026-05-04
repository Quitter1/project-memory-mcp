"""
空库初始化 — 复制配置模板，创建必要目录，初始化空 memory.db。

使用：
    python scripts/bootstrap_empty.py
    python scripts/bootstrap_empty.py --force --yes
"""

import shutil
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))


def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def main():
    args = sys.argv[1:]
    force = "--force" in args
    yes = "--yes" in args

    ok_count = 0

    # 1. 确保目录存在
    for d in ["data", "logs", "reviews", "backups"]:
        _ensure_dir(_PROJECT_ROOT / d)

    # 2. 复制 server.yml
    server_yml = _PROJECT_ROOT / "config" / "server.yml"
    server_example = _PROJECT_ROOT / "config" / "server.example.yml"

    if server_yml.exists() and not force:
        print("[OK] config/server.yml (已存在，跳过)")
        ok_count += 1
    else:
        if server_yml.exists() and force:
            if not yes:
                print("[WARN] --force 将覆盖 config/server.yml。请加 --yes 确认")
                return 1
        if server_example.exists():
            shutil.copy(str(server_example), str(server_yml))
            print("[OK] config/server.yml (从 example 复制)")
            ok_count += 1
        else:
            print("[FAIL] config/server.example.yml 不存在")

    # 3. 复制 projects.yml
    projects_yml = _PROJECT_ROOT / "config" / "projects.yml"
    projects_example = _PROJECT_ROOT / "config" / "projects.example.yml"

    if projects_yml.exists() and not force:
        print("[OK] config/projects.yml (已存在，跳过)")
        ok_count += 1
    else:
        if projects_yml.exists() and force:
            if not yes:
                print("[WARN] --force 将覆盖 config/projects.yml。请加 --yes 确认")
                return 1
        if projects_example.exists():
            shutil.copy(str(projects_example), str(projects_yml))
            print("[OK] config/projects.yml (从 example 复制)")
            ok_count += 1
        else:
            print("[FAIL] config/projects.example.yml 不存在")

    # 4. 初始化空数据库
    db_path = _PROJECT_ROOT / "data" / "memory.db"
    if db_path.exists() and not force:
        print("[OK] data/memory.db (已存在，跳过)")
    else:
        import _paths
        _ = _paths.ensure_import_paths()
        from project_memory_mcp.app_context import AppContext

        config_dir = _PROJECT_ROOT / "config"
        ctx = AppContext(config_dir=config_dir, db_path=db_path)
        ctx.sync_projects()
        ctx.db.close()
        print("[OK] data/memory.db 已初始化")

    print("")
    print("Next:")
    print("  python scripts/check_embedding.py")
    print("  python scripts/check_qdrant.py --warmup")
    print("  python scripts/reindex_vectors.py --yes")
    print("  python scripts/diagnose.py --vector-summary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

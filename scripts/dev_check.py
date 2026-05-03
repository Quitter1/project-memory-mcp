"""
开发环境健康检查。

使用：
    python scripts/dev_check.py

环境变量：
    PROJECT_MEMORY_CONFIG_DIR / PROJECT_MEMORY_DB_PATH

exit code 0 = 一切正常, 非0 = 有问题
"""

import sys
import sqlite3
from pathlib import Path

import _paths
_ = _paths.ensure_import_paths()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


_exit_code = 0


def _ok(msg: str):
    print(f"  [OK] {msg}")


def _fail(msg: str):
    global _exit_code
    print(f"  [FAIL] {msg}")
    _exit_code = 1


def check_python():
    print("1. Python 版本")
    v = sys.version_info
    print(f"   Python {v.major}.{v.minor}.{v.micro}")
    if v >= (3, 10):
        _ok("Python >= 3.10")
    else:
        _fail(f"需要 Python >= 3.10, 当前 {v.major}.{v.minor}")


def check_dirs():
    print("\n2. 关键目录")
    for d in ["config", "data", "docs", "src", "tests", "scripts", "sandbox"]:
        p = _PROJECT_ROOT / d
        if p.is_dir():
            _ok(str(p.relative_to(_PROJECT_ROOT)))
        else:
            _fail(f"{d} 目录不存在")


def check_config(config_dir: Path):
    print("\n3. 配置文件")
    yml = config_dir / "projects.yml"
    if yml.exists():
        _ok(f"projects.yml ({yml.stat().st_size} bytes)")
    else:
        _fail(f"projects.yml 不存在: {yml}")


def check_db(db_path: Path):
    print("\n4. SQLite 数据库")
    if not db_path.exists():
        _fail(f"memory.db 不存在: {db_path}（请先 python scripts/init_db.py）")
        return

    _ok(f"memory.db ({db_path.stat().st_size} bytes)")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    r = conn.execute("PRAGMA user_version").fetchone()
    uv = r[0]
    print(f"   user_version = {uv}")
    if uv >= 2:
        _ok("user_version >= 2")
    else:
        _fail(f"user_version = {uv}, 期望 >= 2")

    r = conn.execute("PRAGMA journal_mode").fetchone()
    jm = r[0]
    print(f"   journal_mode = {jm}")
    if jm == "wal":
        _ok("journal_mode = wal")
    else:
        _fail(f"journal_mode = {jm}, 期望 wal")

    r = conn.execute("PRAGMA foreign_keys").fetchone()
    fk = r[0]
    print(f"   foreign_keys = {fk}")
    if fk == 1:
        _ok("foreign_keys = ON")
    else:
        _fail(f"foreign_keys = {fk}, 期望 1")

    n_projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    print(f"   projects = {n_projects}")

    n_memories = conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
    print(f"   memory_items = {n_memories}")

    n_audit = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    print(f"   audit_log = {n_audit}")

    conn.close()


def check_config_loader(config_dir: Path):
    print("\n5. ConfigLoader")
    try:
        from project_memory_mcp.config.loader import ConfigLoader
        cl = ConfigLoader(str(config_dir))
        projects = cl.load_all_projects()
        _ok(f"加载了 {len(projects)} 个项目")
    except Exception as e:
        _fail(f"ConfigLoader 失败: {e}")


def check_app_context(config_dir: Path, db_path: Path):
    print("\n6. AppContext")
    try:
        from project_memory_mcp.app_context import AppContext
        ctx = AppContext(config_dir=config_dir, db_path=db_path)
        _ok("AppContext 初始化成功")
        ctx.db.close()
    except Exception as e:
        _fail(f"AppContext 初始化失败: {e}")


def main():
    config_dir, db_path = _paths.get_project_paths()

    print("=" * 50)
    print("  Project Memory MCP — 开发环境健康检查")
    print("=" * 50)
    check_python()
    check_dirs()
    check_config(config_dir)
    check_db(db_path)
    check_config_loader(config_dir)
    check_app_context(config_dir, db_path)
    print(f"\n{'=' * 50}")
    if _exit_code == 0:
        print("  全部检查通过")
    else:
        print("  存在失败项，请检查上述 [FAIL]")
    print(f"{'=' * 50}")
    return _exit_code


if __name__ == "__main__":
    sys.exit(main())

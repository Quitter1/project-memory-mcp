"""
开发环境健康检查。

检查项：Python版本、目录、配置文件、数据库、服务初始化。

使用：
    python scripts/dev_check.py
    # exit code 0 = 一切正常, 非0 = 有问题
"""

import os
import sys
import sqlite3
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
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
        _fail(f"需要 Python >= 3.10，当前 {v.major}.{v.minor}")


def check_dirs():
    print("\n2. 关键目录")
    for d in ["config", "data", "docs", "src", "tests", "scripts", "sandbox"]:
        p = _PROJECT_ROOT / d
        if p.is_dir():
            _ok(str(p.relative_to(_PROJECT_ROOT)))
        else:
            _fail(f"{d} 目录不存在")


def check_config():
    print("\n3. 配置文件")
    yml = _PROJECT_ROOT / "config" / "projects.yml"
    if yml.exists():
        _ok(f"projects.yml ({yml.stat().st_size} bytes)")
    else:
        _fail("config/projects.yml 不存在")


def check_db():
    print("\n4. SQLite 数据库")
    db = _PROJECT_ROOT / "data" / "memory.db"
    if not db.exists():
        _fail("data/memory.db 不存在（请先 python scripts/init_db.py）")
        return

    _ok(f"memory.db ({db.stat().st_size} bytes)")
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row

    r = conn.execute("PRAGMA user_version").fetchone()
    print(f"   user_version = {r[0]}")

    r = conn.execute("PRAGMA journal_mode").fetchone()
    print(f"   journal_mode = {r[0]}")

    r = conn.execute("PRAGMA foreign_keys").fetchone()
    print(f"   foreign_keys = {r[0]}")

    n_projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    print(f"   projects = {n_projects}")

    n_memories = conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
    print(f"   memory_items = {n_memories}")

    n_audit = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    print(f"   audit_log = {n_audit}")

    conn.close()


def check_config_loader():
    print("\n5. ConfigLoader")
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))
    try:
        from project_memory_mcp.config.loader import ConfigLoader
        cl = ConfigLoader(str(_PROJECT_ROOT / "config"))
        projects = cl.load_all_projects()
        _ok(f"加载了 {len(projects)} 个项目")
    except Exception as e:
        _fail(f"ConfigLoader 失败: {e}")


def check_app_context():
    print("\n6. AppContext")
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))
    try:
        from project_memory_mcp.app_context import AppContext
        ctx = AppContext(
            config_dir=_PROJECT_ROOT / "config",
            db_path=_PROJECT_ROOT / "data" / "memory.db",
        )
        _ok("AppContext 初始化成功")
        ctx.db.close()
    except Exception as e:
        _fail(f"AppContext 初始化失败: {e}")


def main():
    print("=" * 50)
    print("  Project Memory MCP — 开发环境健康检查")
    print("=" * 50)
    check_python()
    check_dirs()
    check_config()
    check_db()
    check_config_loader()
    check_app_context()
    print(f"\n{'=' * 50}")
    if _exit_code == 0:
        print("  全部检查通过")
    else:
        print("  存在失败项，请检查上述 [FAIL]")
    print(f"{'=' * 50}")
    return _exit_code


if __name__ == "__main__":
    sys.exit(main())

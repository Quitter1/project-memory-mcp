"""
初始化数据库脚本。

使用方法：
    python scripts/init_db.py [--db-path data/memory.db]

创建 SQLite 数据库、执行 schema 迁移、验证表结构。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from project_memory_mcp.db.connection import DatabaseConnection
from project_memory_mcp.db.migrations import get_current_version, LATEST_VERSION


def main():
    """初始化数据库。"""
    db_path = "data/memory.db"
    if len(sys.argv) > 2 and sys.argv[1] == "--db-path":
        db_path = sys.argv[2]

    db = DatabaseConnection(db_path)
    conn = db.connect()

    version = get_current_version(conn)
    print(f"数据库路径: {db_path}")
    print(f"WAL 模式: {conn.execute('PRAGMA journal_mode').fetchone()[0]}")
    print(f"foreign_keys: {conn.execute('PRAGMA foreign_keys').fetchone()[0]}")
    print(f"Schema 版本: {version} (最新: {LATEST_VERSION})")

    # 验证表存在
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print(f"已创建表 ({len(tables)}):")
    for t in tables:
        print(f"  - {t['name']}")

    db.close()
    print("数据库初始化完成。")


if __name__ == "__main__":
    main()

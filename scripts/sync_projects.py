"""
将 config/projects.yml 同步到 SQLite。

使用方法：
    python scripts/sync_projects.py [--config config/] [--db-path data/memory.db]

功能：
1. 读取 projects.yml
2. 对每个项目执行 UPSERT 到 SQLite
3. 计算 yaml_hash 检测变更
4. 写 audit_log
5. 不删除 archived/disabled 项目的历史知识
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from project_memory_mcp.config.loader import ConfigLoader, ConfigError
from project_memory_mcp.db.connection import DatabaseConnection
from project_memory_mcp.project.manager import ProjectManager


def main():
    """同步项目配置。"""
    config_dir = "config"
    db_path = "data/memory.db"

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--config" and i + 1 < len(args):
            config_dir = args[i + 1]
            i += 2
        elif args[i] == "--db-path" and i + 1 < len(args):
            db_path = args[i + 1]
            i += 2
        else:
            i += 1

    print(f"配置目录: {config_dir}")
    print(f"数据库路径: {db_path}")

    # 加载配置
    try:
        loader = ConfigLoader(config_dir)
        yaml_projects = loader.load_all_projects()
        yaml_hash = loader.compute_yaml_hash()
        print(f"YAML 中项目数: {len(yaml_projects)}")
        print(f"YAML hash: {yaml_hash[:16]}...")
    except ConfigError as e:
        print(f"配置错误: {e}")
        sys.exit(1)

    # 连接数据库
    db = DatabaseConnection(db_path)
    conn = db.connect()

    # 同步
    from project_memory_mcp.db.project_repo import ProjectRepository
    from project_memory_mcp.db.audit_repo import AuditRepository

    project_repo = ProjectRepository(conn)
    manager = ProjectManager(project_repo, loader)

    result = manager.sync_from_yaml(actor="sync_projects")
    print(f"同步结果: 创建 {result['created']}, 更新 {result['updated']}, 总计 {result['total_in_yaml']}")

    # 显示项目列表
    print("\n当前项目:")
    for p in project_repo.list_projects("all"):
        print(f"  [{p.status:8s}] {p.id:20s} | {p.name}")

    db.close()
    print("\n同步完成。")


if __name__ == "__main__":
    main()

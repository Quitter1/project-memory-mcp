"""AppContext — 集中初始化所有服务，供 MCP server 和 tool handlers 共享。

规则：
- 初始化时自动执行数据库迁移
- 所有 tool handler 共享同一个 context 实例
- 测试时可传入临时 db_path 和 config_dir
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config.loader import ConfigLoader
from .db.connection import DatabaseConnection
from .db.migrations import run_migrations
from .db.project_repo import ProjectRepository
from .db.memory_repo import MemoryRepository
from .db.audit_repo import AuditRepository
from .project.resolver import ProjectResolver
from .project.manager import ProjectManager
from .project.profile import ProjectProfileBuilder
from .retrieval.search import KnowledgeSearchService
from .knowledge.validator import ContentValidator
from .knowledge.deduplicator import Deduplicator
from .knowledge.lifecycle import LifecycleManager
from .knowledge.reviewer import RuleBasedReviewer
from .knowledge.governance import KnowledgeGovernance


@dataclass
class AppContext:
    """应用上下文，集中管理所有服务实例。"""

    config_dir: Path
    db_path: Path
    conn: sqlite3.Connection = field(init=False)
    db: DatabaseConnection = field(init=False)
    config_loader: ConfigLoader = field(init=False)
    project_repo: ProjectRepository = field(init=False)
    memory_repo: MemoryRepository = field(init=False)
    audit_repo: AuditRepository = field(init=False)
    resolver: ProjectResolver = field(init=False)
    project_manager: ProjectManager = field(init=False)
    profile_builder: ProjectProfileBuilder = field(init=False)
    search_service: KnowledgeSearchService = field(init=False)
    validator: ContentValidator = field(init=False)
    deduplicator: Deduplicator = field(init=False)
    reviewer: RuleBasedReviewer = field(init=False)
    governance: KnowledgeGovernance = field(init=False)

    def __post_init__(self):
        # 1. 数据库连接 + 迁移
        self.db = DatabaseConnection(str(self.db_path))
        self.conn = self.db.connect()
        run_migrations(self.conn)

        # 2. Repositories
        self.project_repo = ProjectRepository(self.conn)
        self.memory_repo = MemoryRepository(self.conn)
        self.audit_repo = AuditRepository(self.conn)

        # 3. 配置加载
        self.config_loader = ConfigLoader(str(self.config_dir))

        # 4. 项目识别
        self.resolver = ProjectResolver(self.project_repo, self.config_loader)
        self.project_manager = ProjectManager(self.project_repo, self.config_loader)
        self.profile_builder = ProjectProfileBuilder(self.memory_repo, self.project_repo)

        # 5. 检索服务（MVP 不接 Qdrant）
        self.search_service = KnowledgeSearchService(
            conn=self.conn,
            vector_store=None,
            embedder=None,
        )

        # 6. 知识治理
        self.validator = ContentValidator()
        self.deduplicator = Deduplicator(
            repo=self.memory_repo,
            vector_store=None,
            embedder=None,
        )
        self.reviewer = RuleBasedReviewer()
        self.governance = KnowledgeGovernance(
            repo=self.memory_repo,
            audit=self.audit_repo,
            validator=self.validator,
            deduplicator=self.deduplicator,
            reviewer=self.reviewer,
        )

    def sync_projects(self) -> int:
        """将 projects.yml 同步到 SQLite。返回同步数量。"""
        result = self.project_manager.sync_from_yaml()
        return result.get("created", 0) + result.get("updated", 0)

    @classmethod
    def create_for_test(cls, config_dir: Path, db_path: Path) -> "AppContext":
        """创建测试用 context（可指定临时路径）。"""
        config_dir.mkdir(parents=True, exist_ok=True)
        return cls(config_dir=config_dir, db_path=db_path)

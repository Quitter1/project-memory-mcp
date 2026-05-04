"""AppContext — 集中初始化所有服务，供 MCP server 和 tool handlers 共享。

规则：
- 初始化时自动执行数据库迁移
- 所有 tool handler 共享同一个 context 实例
- 测试时可传入临时 db_path 和 config_dir
"""

import logging
import os
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
    embedder: object = field(init=False, default=None)
    vector_store: object = field(init=False, default=None)
    vector_indexer: object = field(init=False, default=None)
    validator: ContentValidator = field(init=False)
    deduplicator: Deduplicator = field(init=False)
    reviewer: RuleBasedReviewer = field(init=False)
    governance: KnowledgeGovernance = field(init=False)

    def __post_init__(self):
        # 0. 日志初始化
        self._init_logging()

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

        # 5. 检索服务 + 向量
        self._init_vector()
        import yaml
        search_cfg = {}
        server_yml = self.config_dir / "server.yml"
        if server_yml.exists():
            try:
                raw = yaml.safe_load(server_yml.read_text(encoding="utf-8"))
                search_cfg = raw.get("search", {}) if raw else {}
            except Exception:
                pass
        self.search_service = KnowledgeSearchService(
            conn=self.conn,
            vector_store=self.vector_store,
            embedder=self.embedder,
            search_config=search_cfg,
        )

        # 6. 知识治理
        self.validator = ContentValidator()
        self.deduplicator = Deduplicator(
            repo=self.memory_repo,
            vector_store=None,
            embedder=None,
        )
        self.reviewer = RuleBasedReviewer()
        from .llm.config import LLMReviewerConfig
        import yaml as _yaml
        llm_cfg = LLMReviewerConfig()
        srv = self.config_dir / "server.yml"
        if srv.exists():
            try:
                raw = _yaml.safe_load(srv.read_text(encoding="utf-8"))
                llm_cfg = LLMReviewerConfig.from_server_config(raw)
            except Exception:
                pass

        llm_reviewer = None
        if llm_cfg.is_configured():
            from .llm.reviewer import LLMReviewer
            llm_reviewer = LLMReviewer(llm_cfg)

        self.governance = KnowledgeGovernance(
            repo=self.memory_repo,
            audit=self.audit_repo,
            validator=self.validator,
            deduplicator=self.deduplicator,
            reviewer=self.reviewer,
            indexer=self.vector_indexer,
            llm_reviewer=llm_reviewer,
        )

        # 7. 启动就绪日志
        self._log_ready()

    def _init_logging(self):
        """读取 server.yml + 环境变量初始化日志。"""
        from .utils.logging import setup_logging
        import yaml

        server_yml = self.config_dir / "server.yml"
        cfg: dict = {}
        if server_yml.exists():
            try:
                raw = yaml.safe_load(server_yml.read_text(encoding="utf-8"))
                cfg = raw.get("logging", {}) if raw else {}
            except Exception:
                cfg = {}

        log_dir = os.environ.get("PROJECT_MEMORY_LOG_DIR")
        if not log_dir:
            log_dir = cfg.get("log_dir")
            if log_dir:
                log_dir = str(self.config_dir.parent / log_dir)
            else:
                log_dir = self.config_dir.parent / "logs"

        log_level = os.environ.get("PROJECT_MEMORY_LOG_LEVEL") or cfg.get("level", "INFO")
        file_enabled = cfg.get("file_enabled", True)
        stderr_enabled = cfg.get("stderr_enabled", True)

        setup_logging(
            log_dir=Path(log_dir), level=str(log_level),
            enable_file=bool(file_enabled), enable_stderr=bool(stderr_enabled),
            max_bytes=int(cfg.get("max_bytes", 5 * 1024 * 1024)),
            backup_count=int(cfg.get("backup_count", 5)),
        )
        logging.getLogger("project_memory_mcp").info(
            "app_context_start config_dir=%s db_path=%s", self.config_dir, self.db_path,
        )

    def _init_vector(self):
        """初始化向量组件（Qdrant disabled 时跳过）。"""
        import yaml
        server_yml = self.config_dir / "server.yml"
        qdrant_cfg = {}
        embed_cfg = {}
        if server_yml.exists():
            try:
                raw = yaml.safe_load(server_yml.read_text(encoding="utf-8"))
                qdrant_cfg = raw.get("qdrant", {}) if raw else {}
                embed_cfg = raw.get("embedding", {}) if raw else {}
            except Exception:
                pass

        if not qdrant_cfg.get("enabled", False) and not embed_cfg.get("enabled", False):
            self.embedder = None
            self.vector_store = None
            self.vector_indexer = None
            return

        # Embedding
        dim = embed_cfg.get("dim", 512)
        provider = embed_cfg.get("provider", "hashing")
        if provider == "http":
            try:
                from .vector.embeddings import HttpEmbeddingProvider
                http_cfg = embed_cfg.get("http", {})
                self.embedder = HttpEmbeddingProvider(
                    base_url=http_cfg.get("base_url", "http://127.0.0.1:8008"),
                    endpoint=http_cfg.get("endpoint", "/embed_text"),
                    dim=dim, model=embed_cfg.get("model", "http-v1"),
                    timeout_seconds=http_cfg.get("timeout_seconds", 30),
                )
            except Exception:
                self.embedder = None
        else:
            from .vector.embeddings import HashingEmbeddingProvider
            self.embedder = HashingEmbeddingProvider(dim=dim, model=embed_cfg.get("model", "hashing-v1"))

        # Qdrant
        if qdrant_cfg.get("enabled", False):
            try:
                from .vector.qdrant_store import QdrantVectorStore
                self.vector_store = QdrantVectorStore(
                    host=qdrant_cfg.get("host", "127.0.0.1"),
                    port=qdrant_cfg.get("http_port", 6333),
                    collection=qdrant_cfg.get("collection", "project_memory_items"),
                    vector_dim=dim,
                    timeout_seconds=qdrant_cfg.get("timeout_seconds", 10),
                    prefer_grpc=qdrant_cfg.get("prefer_grpc", False),
                )
                if self.embedder is not None:
                    from .vector.indexer import VectorIndexer
                    self.vector_indexer = VectorIndexer(
                        self.memory_repo, self.embedder, self.vector_store,
                    )
            except Exception:
                self.vector_store = None
                self.vector_indexer = None
        else:
            self.vector_store = None
            self.vector_indexer = None

    def _log_ready(self):
        """记录启动就绪摘要。"""
        try:
            uv = self.conn.execute("PRAGMA user_version").fetchone()[0]
            n_p = self.conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            n_m = self.conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
            n_a = self.conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        except Exception:
            uv, n_p, n_m, n_a = "?", "?", "?", "?"

        logging.getLogger("project_memory_mcp").info(
            "app_context_ready user_version=%s project_count=%s memory_count=%s "
            "audit_log_count=%s qdrant_enabled=%s embedding_enabled=%s search_mode=%s",
            uv, n_p, n_m, n_a,
            "true" if self.vector_store is not None else "false",
            "true" if self.embedder is not None else "false",
            getattr(self.search_service, "mode", "keyword"),
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

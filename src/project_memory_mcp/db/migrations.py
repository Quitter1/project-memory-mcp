"""Schema 版本化迁移管理 — 使用 PRAGMA user_version 追踪版本。"""

import sqlite3
import logging

logger = logging.getLogger("project_memory_mcp")

# 当前最新 schema 版本
LATEST_VERSION = 2

# 迁移列表：[(version, description, sql), ...]
MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "initial schema — projects, memory_items, memory_tags, memory_relations, audit_log",
        """
        -- 项目表（运行时缓存，配置源为 projects.yml）
        CREATE TABLE IF NOT EXISTS projects (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            slug            TEXT NOT NULL UNIQUE,
            description     TEXT DEFAULT '',
            status          TEXT NOT NULL DEFAULT 'active',
            root_paths      TEXT NOT NULL DEFAULT '[]',
            path_patterns   TEXT NOT NULL DEFAULT '[]',
            aliases         TEXT NOT NULL DEFAULT '[]',
            tech_stack      TEXT NOT NULL DEFAULT '[]',
            module_keywords TEXT NOT NULL DEFAULT '[]',
            default_confidence      REAL DEFAULT 0.5,
            auto_approve_threshold  REAL DEFAULT -1,
            max_candidate_per_task  INTEGER DEFAULT 20,
            retention_days          INTEGER DEFAULT 365,
            review_policy   TEXT NOT NULL DEFAULT '{}',
            metadata        TEXT NOT NULL DEFAULT '{}',
            superseded_by   TEXT,
            merged_into     TEXT,
            yaml_hash       TEXT DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- 知识条目主表
        CREATE TABLE IF NOT EXISTS memory_items (
            id              TEXT PRIMARY KEY,
            project_id      TEXT NOT NULL,
            module          TEXT NOT NULL DEFAULT '',
            type            TEXT NOT NULL,
            title           TEXT NOT NULL,
            content         TEXT NOT NULL,
            content_hash    TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'candidate',
            index_status    TEXT NOT NULL DEFAULT 'not_indexed',
            confidence      REAL NOT NULL DEFAULT 0.5,
            risk_level      TEXT NOT NULL DEFAULT 'low',
            scope           TEXT NOT NULL DEFAULT 'project',
            allowed_projects TEXT NOT NULL DEFAULT '[]',
            denied_projects  TEXT NOT NULL DEFAULT '[]',
            source_type     TEXT NOT NULL DEFAULT 'ai_inferred',
            source_task_id  TEXT,
            source_agent    TEXT,
            source_evidence TEXT NOT NULL DEFAULT '{}',
            source_file     TEXT,
            source_line     INTEGER,
            parent_id       TEXT,
            superseded_by   TEXT,
            created_by      TEXT,
            reviewed_by     TEXT,
            review_comment  TEXT,
            embedding_model TEXT,
            vector_id       TEXT,
            metadata        TEXT NOT NULL DEFAULT '{}',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
            reviewed_at     TEXT,
            expires_at      TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        -- 知识标签（多对多，支持按表名、字段名、文件名、类名检索）
        CREATE TABLE IF NOT EXISTS memory_tags (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id   TEXT NOT NULL,
            tag         TEXT NOT NULL,
            category    TEXT NOT NULL DEFAULT 'general',
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (memory_id) REFERENCES memory_items(id) ON DELETE CASCADE
        );

        -- 知识关联
        CREATE TABLE IF NOT EXISTS memory_relations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id_a     TEXT NOT NULL,
            memory_id_b     TEXT NOT NULL,
            relation_type   TEXT NOT NULL,
            description     TEXT DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (memory_id_a) REFERENCES memory_items(id) ON DELETE CASCADE,
            FOREIGN KEY (memory_id_b) REFERENCES memory_items(id) ON DELETE CASCADE
        );

        -- 审计日志
        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  TEXT,
            memory_id   TEXT,
            action      TEXT NOT NULL,
            old_value   TEXT,
            new_value   TEXT,
            actor       TEXT,
            reason      TEXT,
            task_id     TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- 索引
        CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
        CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(slug);
        CREATE INDEX IF NOT EXISTS idx_memory_project_id ON memory_items(project_id);
        CREATE INDEX IF NOT EXISTS idx_memory_status ON memory_items(status);
        CREATE INDEX IF NOT EXISTS idx_memory_index_status ON memory_items(index_status);
        CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory_items(scope);
        CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_items(type);
        CREATE INDEX IF NOT EXISTS idx_memory_module ON memory_items(module);
        CREATE INDEX IF NOT EXISTS idx_memory_content_hash ON memory_items(content_hash);
        CREATE INDEX IF NOT EXISTS idx_memory_risk_level ON memory_items(risk_level);
        CREATE INDEX IF NOT EXISTS idx_memory_project_status ON memory_items(project_id, status);
        CREATE INDEX IF NOT EXISTS idx_memory_project_scope ON memory_items(project_id, scope);
        CREATE INDEX IF NOT EXISTS idx_memory_scope_status ON memory_items(scope, status);
        CREATE INDEX IF NOT EXISTS idx_tags_memory ON memory_tags(memory_id);
        CREATE INDEX IF NOT EXISTS idx_tags_tag ON memory_tags(tag);
        CREATE INDEX IF NOT EXISTS idx_tags_category ON memory_tags(category);
        CREATE INDEX IF NOT EXISTS idx_relations_a ON memory_relations(memory_id_a);
        CREATE INDEX IF NOT EXISTS idx_relations_b ON memory_relations(memory_id_b);
        CREATE INDEX IF NOT EXISTS idx_relation_type ON memory_relations(relation_type);
        CREATE INDEX IF NOT EXISTS idx_audit_project ON audit_log(project_id);
        CREATE INDEX IF NOT EXISTS idx_audit_memory ON audit_log(memory_id);
        CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
        CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
        """,
    ),
    (
        2,
        "unique constraints — memory_tags + memory_relations dedup and unique indexes",
        """
        -- 先去重 tags
        DELETE FROM memory_tags
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM memory_tags
            GROUP BY memory_id, tag, category
        );

        -- 先去重 relations
        DELETE FROM memory_relations
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM memory_relations
            GROUP BY memory_id_a, memory_id_b, relation_type
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_tags_unique
        ON memory_tags(memory_id, tag, category);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_relations_unique
        ON memory_relations(memory_id_a, memory_id_b, relation_type);
        """,
    ),
]


def get_current_version(conn: sqlite3.Connection) -> int:
    """获取当前 schema 版本。"""
    row = conn.execute("PRAGMA user_version").fetchone()
    return row[0] if row else 0


def set_version(conn: sqlite3.Connection, version: int) -> None:
    """设置 schema 版本。"""
    conn.execute(f"PRAGMA user_version = {version}")


def run_migrations(conn: sqlite3.Connection) -> None:
    """执行所有未应用的迁移。"""
    current = get_current_version(conn)
    for version, description, sql in MIGRATIONS:
        if version > current:
            logger.info("迁移 v%d → v%d: %s", current, version, description)
            conn.executescript(sql)
            set_version(conn, version)
            current = version
            logger.info("迁移 v%d 完成", version)

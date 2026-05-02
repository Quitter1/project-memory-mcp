"""Project CRUD 仓库。"""

import json
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from ..models.project import Project
from .audit_repo import AuditRepository


class ProjectRepository:
    """项目数据访问层。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.audit = AuditRepository(conn)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_by_id(self, project_id: str) -> Optional[Project]:
        """按 ID 查询项目。"""
        row = self.conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_project(row)

    def list_projects(self, status_filter: str = "all") -> list[Project]:
        """列出项目（可按状态过滤）。"""
        if status_filter == "all":
            rows = self.conn.execute(
                "SELECT * FROM projects ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM projects WHERE status = ? ORDER BY created_at DESC",
                (status_filter,),
            ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def list_active(self) -> list[Project]:
        """列出所有 active 项目。"""
        return self.list_projects("active")

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def upsert_project(
        self,
        project: Project,
        actor: str = "system",
        reason: str = "",
    ) -> Project:
        """
        UPSERT 项目。存在则更新，不存在则插入。
        自动记录 audit_log。
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        existing = self.get_by_id(project.id)
        if existing is not None:
            # 更新
            old_json = self._project_to_json(existing)
            self.conn.execute(
                """UPDATE projects SET
                    name=:name, slug=:slug, description=:description,
                    status=:status, root_paths=:root_paths, path_patterns=:path_patterns,
                    aliases=:aliases, tech_stack=:tech_stack, module_keywords=:module_keywords,
                    default_confidence=:default_confidence, auto_approve_threshold=:auto_approve_threshold,
                    max_candidate_per_task=:max_candidate_per_task, retention_days=:retention_days,
                    review_policy=:review_policy, metadata=:metadata,
                    superseded_by=:superseded_by, merged_into=:merged_into,
                    yaml_hash=:yaml_hash, updated_at=:updated_at
                WHERE id=:id""",
                {
                    "id": project.id,
                    "name": project.name,
                    "slug": project.slug,
                    "description": project.description,
                    "status": project.status,
                    "root_paths": json.dumps(project.root_paths, ensure_ascii=False),
                    "path_patterns": json.dumps(project.path_patterns, ensure_ascii=False),
                    "aliases": json.dumps(project.aliases, ensure_ascii=False),
                    "tech_stack": json.dumps(project.tech_stack, ensure_ascii=False),
                    "module_keywords": json.dumps(project.module_keywords, ensure_ascii=False),
                    "default_confidence": project.default_confidence,
                    "auto_approve_threshold": project.auto_approve_threshold,
                    "max_candidate_per_task": project.max_candidate_per_task,
                    "retention_days": project.retention_days,
                    "review_policy": json.dumps(project.review_policy, ensure_ascii=False),
                    "metadata": json.dumps(project.metadata, ensure_ascii=False),
                    "superseded_by": project.superseded_by,
                    "merged_into": project.merged_into,
                    "yaml_hash": project.yaml_hash,
                    "updated_at": now,
                },
            )
            action = "project_updated"
        else:
            # 插入
            project.created_at = now
            project.updated_at = now
            self.conn.execute(
                """INSERT INTO projects (
                    id, name, slug, description, status,
                    root_paths, path_patterns, aliases, tech_stack, module_keywords,
                    default_confidence, auto_approve_threshold, max_candidate_per_task,
                    retention_days, review_policy, metadata,
                    superseded_by, merged_into, yaml_hash,
                    created_at, updated_at
                ) VALUES (
                    :id, :name, :slug, :description, :status,
                    :root_paths, :path_patterns, :aliases, :tech_stack, :module_keywords,
                    :default_confidence, :auto_approve_threshold, :max_candidate_per_task,
                    :retention_days, :review_policy, :metadata,
                    :superseded_by, :merged_into, :yaml_hash,
                    :created_at, :updated_at
                )""",
                {
                    "id": project.id,
                    "name": project.name,
                    "slug": project.slug,
                    "description": project.description,
                    "status": project.status,
                    "root_paths": json.dumps(project.root_paths, ensure_ascii=False),
                    "path_patterns": json.dumps(project.path_patterns, ensure_ascii=False),
                    "aliases": json.dumps(project.aliases, ensure_ascii=False),
                    "tech_stack": json.dumps(project.tech_stack, ensure_ascii=False),
                    "module_keywords": json.dumps(project.module_keywords, ensure_ascii=False),
                    "default_confidence": project.default_confidence,
                    "auto_approve_threshold": project.auto_approve_threshold,
                    "max_candidate_per_task": project.max_candidate_per_task,
                    "retention_days": project.retention_days,
                    "review_policy": json.dumps(project.review_policy, ensure_ascii=False),
                    "metadata": json.dumps(project.metadata, ensure_ascii=False),
                    "superseded_by": project.superseded_by,
                    "merged_into": project.merged_into,
                    "yaml_hash": project.yaml_hash,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            action = "project_created"

        # 在同一连接内读取未提交的变更
        new_project = self.get_by_id(project.id)

        # 审计日志（与数据写入在同一事务内）
        self.audit.log_action(
            project_id=project.id,
            action=action,
            old_value=self._project_to_json(existing) if existing else None,
            new_value=self._project_to_json(new_project),
            actor=actor,
            reason=reason,
        )

        self.conn.commit()
        return new_project

    def update_status(
        self,
        project_id: str,
        new_status: str,
        actor: str = "system",
        reason: str = "",
    ) -> Optional[Project]:
        """更新项目状态。"""
        existing = self.get_by_id(project_id)
        if existing is None:
            return None

        old_json = self._project_to_json(existing)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        self.conn.execute(
            "UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, project_id),
        )

        updated = self.get_by_id(project_id)
        self.audit.log_action(
            project_id=project_id,
            action="project_status_changed",
            old_value=old_json,
            new_value=self._project_to_json(updated),
            actor=actor,
            reason=reason,
        )

        self.conn.commit()
        return updated

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> Project:
        """sqlite3.Row → Project dataclass。"""
        return Project(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            description=row["description"] or "",
            status=row["status"],
            root_paths=json.loads(row["root_paths"]) if row["root_paths"] else [],
            path_patterns=json.loads(row["path_patterns"]) if row["path_patterns"] else [],
            aliases=json.loads(row["aliases"]) if row["aliases"] else [],
            tech_stack=json.loads(row["tech_stack"]) if row["tech_stack"] else [],
            module_keywords=json.loads(row["module_keywords"]) if row["module_keywords"] else [],
            default_confidence=row["default_confidence"] if row["default_confidence"] is not None else 0.5,
            auto_approve_threshold=row["auto_approve_threshold"] if row["auto_approve_threshold"] is not None else -1,
            max_candidate_per_task=row["max_candidate_per_task"] if row["max_candidate_per_task"] is not None else 20,
            retention_days=row["retention_days"] if row["retention_days"] is not None else 365,
            review_policy=json.loads(row["review_policy"]) if row["review_policy"] else {},
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            superseded_by=row["superseded_by"],
            merged_into=row["merged_into"],
            yaml_hash=row["yaml_hash"] or "",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )

    @staticmethod
    def _project_to_json(project: Optional[Project]) -> str:
        """Project → JSON 字符串（用于 audit_log）。"""
        if project is None:
            return "null"
        return json.dumps(
            {
                "id": project.id,
                "name": project.name,
                "slug": project.slug,
                "status": project.status,
                "root_paths": project.root_paths,
                "aliases": project.aliases,
                "tech_stack": project.tech_stack,
                "auto_approve_threshold": project.auto_approve_threshold,
            },
            ensure_ascii=False,
        )

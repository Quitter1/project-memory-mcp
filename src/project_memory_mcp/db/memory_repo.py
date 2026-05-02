"""MemoryItem + memory_tags + memory_relations CRUD 仓库。

规则：
- 不允许物理 DELETE memory_items，所有状态变更通过 update_status
- 所有写操作自动写 audit_log
- ID 使用 uuid.uuid4() 生成
"""

import json
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from ..models.memory_item import MemoryItem
from .audit_repo import AuditRepository


class MemoryRepository:
    """知识条目数据访问层。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.audit = AuditRepository(conn)

    # ==================================================================
    # 查询
    # ==================================================================

    def get_by_id(self, memory_id: str) -> Optional[MemoryItem]:
        """按 ID 查询知识条目。"""
        row = self.conn.execute(
            "SELECT * FROM memory_items WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_memory_item(row)

    def find_by_hash(
        self,
        content_hash: str,
        project_id: str,
        scope: Optional[str] = None,
    ) -> Optional[MemoryItem]:
        """
        按内容哈希 + 项目 ID 查找（用于去重）。

        可选 scope 过滤，避免不同 scope 的同内容知识被误判重复。
        """
        if scope:
            row = self.conn.execute(
                "SELECT * FROM memory_items WHERE content_hash = ? AND project_id = ? "
                "AND scope = ? ORDER BY created_at DESC LIMIT 1",
                (content_hash, project_id, scope),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM memory_items WHERE content_hash = ? AND project_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (content_hash, project_id),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_memory_item(row)

    def list_memories(
        self,
        project_id: str,
        status_filter: Optional[list[str]] = None,
        type_filter: Optional[str] = None,
        module_filter: Optional[str] = None,
        tag_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryItem]:
        """列出项目知识条目（支持多条件过滤）。"""
        conditions = ["project_id = ?"]
        params: list = [project_id]

        if status_filter:
            placeholders = ",".join("?" for _ in status_filter)
            conditions.append(f"status IN ({placeholders})")
            params.extend(status_filter)
        if type_filter:
            conditions.append("type = ?")
            params.append(type_filter)
        if module_filter:
            conditions.append("module = ?")
            params.append(module_filter)
        if tag_filter:
            conditions.append(
                "id IN (SELECT memory_id FROM memory_tags WHERE tag = ?)"
            )
            params.append(tag_filter)

        where = " AND ".join(conditions)
        rows = self.conn.execute(
            f"SELECT * FROM memory_items WHERE {where} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        return [self._row_to_memory_item(r) for r in rows]

    # ==================================================================
    # 写入
    # ==================================================================

    def create_memory(
        self,
        item: MemoryItem,
        actor: str = "system",
        reason: str = "",
        task_id: Optional[str] = None,
    ) -> MemoryItem:
        """
        创建知识条目。

        自动生成 UUID id（如果未提供）。
        """
        if not item.id:
            item.id = str(uuid.uuid4())

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        item.created_at = now
        item.updated_at = now

        self.conn.execute(
            """INSERT INTO memory_items (
                id, project_id, module, type, title, content, content_hash,
                status, index_status, confidence, risk_level,
                scope, allowed_projects, denied_projects,
                source_type, source_task_id, source_agent,
                source_evidence, source_file, source_line,
                parent_id, superseded_by, created_by,
                embedding_model, vector_id, metadata,
                created_at, updated_at
            ) VALUES (
                :id, :project_id, :module, :type, :title, :content, :content_hash,
                :status, :index_status, :confidence, :risk_level,
                :scope, :allowed_projects, :denied_projects,
                :source_type, :source_task_id, :source_agent,
                :source_evidence, :source_file, :source_line,
                :parent_id, :superseded_by, :created_by,
                :embedding_model, :vector_id, :metadata,
                :created_at, :updated_at
            )""",
            {
                "id": item.id,
                "project_id": item.project_id,
                "module": item.module,
                "type": item.type,
                "title": item.title,
                "content": item.content,
                "content_hash": item.content_hash,
                "status": item.status,
                "index_status": item.index_status,
                "confidence": item.confidence,
                "risk_level": item.risk_level,
                "scope": item.scope,
                "allowed_projects": json.dumps(item.allowed_projects, ensure_ascii=False),
                "denied_projects": json.dumps(item.denied_projects, ensure_ascii=False),
                "source_type": item.source_type,
                "source_task_id": item.source_task_id,
                "source_agent": item.source_agent,
                "source_evidence": json.dumps(item.source_evidence, ensure_ascii=False),
                "source_file": item.source_file,
                "source_line": item.source_line,
                "parent_id": item.parent_id,
                "superseded_by": item.superseded_by,
                "created_by": item.created_by or actor,
                "embedding_model": item.embedding_model,
                "vector_id": item.vector_id,
                "metadata": json.dumps(item.metadata, ensure_ascii=False),
                "created_at": now,
                "updated_at": now,
            },
        )

        # 保存标签
        for tag in item.tags:
            self.add_tag(item.id, tag, actor=actor)

        # 在同一连接内读取未提交的变更
        created = self.get_by_id(item.id)

        # 审计日志（与数据写入在同一事务内）
        self.audit.log_action(
            action="memory_created",
            project_id=item.project_id,
            memory_id=item.id,
            new_value=self._item_to_json(created),
            actor=actor,
            reason=reason,
            task_id=task_id,
        )

        self.conn.commit()
        return created

    def update_status(
        self,
        memory_id: str,
        new_status: str,
        actor: str = "system",
        reason: str = "",
        task_id: Optional[str] = None,
    ) -> Optional[MemoryItem]:
        """
        更新知识治理状态（不物理删除）。

        这是所有状态变更的统一入口：
        - candidate → pending_review（审核提交）
        - pending_review → approved（审核通过）
        - pending_review → rejected（审核拒绝）
        - approved → deprecated（废弃）
        - approved → superseded（被替代）
        """
        existing = self.get_by_id(memory_id)
        if existing is None:
            return None

        old_json = self._item_to_json(existing)
        old_status = existing.status
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        self.conn.execute(
            "UPDATE memory_items SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, memory_id),
        )

        updated = self.get_by_id(memory_id)

        # 审计日志（与数据写入在同一事务内）
        self.audit.log_action(
            action="status_changed",
            project_id=updated.project_id if updated else existing.project_id,
            memory_id=memory_id,
            old_value=old_json,
            new_value=self._item_to_json(updated),
            actor=actor,
            reason=f"[{old_status} → {new_status}] {reason}",
            task_id=task_id,
        )

        self.conn.commit()

        return updated

    def update_memory(
        self,
        memory_id: str,
        updates: dict,
        actor: str = "system",
        reason: str = "",
        task_id: Optional[str] = None,
    ) -> Optional[MemoryItem]:
        """
        更新知识条目字段。

        支持更新：title, content, content_hash, module, type, confidence,
        risk_level, scope, source_evidence, source_file, source_line, metadata

        不允许通过此方法修改 status（请用 update_status）。
        """
        existing = self.get_by_id(memory_id)
        if existing is None:
            return None

        old_json = self._item_to_json(existing)

        allowed_fields = {
            "title", "content", "content_hash", "module", "type",
            "confidence", "risk_level", "scope", "source_evidence",
            "source_file", "source_line", "metadata",
            "allowed_projects", "denied_projects", "index_status",
            "embedding_model", "vector_id",
        }

        set_clauses = []
        params: list = []

        for key, value in updates.items():
            if key not in allowed_fields:
                continue
            if key == "source_evidence":
                value = json.dumps(value, ensure_ascii=False)
            elif key in ("allowed_projects", "denied_projects"):
                value = json.dumps(value, ensure_ascii=False)
            elif key == "metadata":
                value = json.dumps(value, ensure_ascii=False)
            set_clauses.append(f"{key} = ?")
            params.append(value)

        if not set_clauses:
            return existing

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        set_clauses.append("updated_at = ?")
        params.append(now)
        params.append(memory_id)

        self.conn.execute(
            f"UPDATE memory_items SET {', '.join(set_clauses)} WHERE id = ?",
            params,
        )

        updated = self.get_by_id(memory_id)

        self.audit.log_action(
            action="memory_updated",
            project_id=updated.project_id if updated else existing.project_id,
            memory_id=memory_id,
            old_value=old_json,
            new_value=self._item_to_json(updated),
            actor=actor,
            reason=reason,
            task_id=task_id,
        )

        self.conn.commit()
        return updated

    # ==================================================================
    # 标签
    # ==================================================================

    def add_tag(
        self,
        memory_id: str,
        tag: str,
        category: str = "general",
        actor: str = "system",
    ) -> None:
        """给知识条目添加标签（调用方负责 commit）。"""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.conn.execute(
            "INSERT OR IGNORE INTO memory_tags (memory_id, tag, category, created_at) "
            "VALUES (?, ?, ?, ?)",
            (memory_id, tag, category, now),
        )

    def remove_tag(self, memory_id: str, tag: str) -> None:
        """移除标签（调用方负责 commit）。"""
        self.conn.execute(
            "DELETE FROM memory_tags WHERE memory_id = ? AND tag = ?",
            (memory_id, tag),
        )

    def list_tags(self, memory_id: str) -> list[dict]:
        """列出知识条目的所有标签。"""
        rows = self.conn.execute(
            "SELECT * FROM memory_tags WHERE memory_id = ? ORDER BY id",
            (memory_id,),
        ).fetchall()
        return [
            {"tag": r["tag"], "category": r["category"], "created_at": r["created_at"]}
            for r in rows
        ]

    # ==================================================================
    # 关联
    # ==================================================================

    def add_relation(
        self,
        memory_id_a: str,
        memory_id_b: str,
        relation_type: str,
        description: str = "",
    ) -> None:
        """
        建立知识关联（调用方负责 commit）。

        校验：
        - memory_id_a != memory_id_b（禁止自引用）
        - relation_type 不能为空
        - 两端 memory 必须存在
        """
        if memory_id_a == memory_id_b:
            raise ValueError("不能将知识与自身关联 (memory_id_a == memory_id_b)")
        if not relation_type or not relation_type.strip():
            raise ValueError("relation_type 不能为空")
        if self.get_by_id(memory_id_a) is None:
            raise ValueError(f"memory_id_a 不存在: {memory_id_a}")
        if self.get_by_id(memory_id_b) is None:
            raise ValueError(f"memory_id_b 不存在: {memory_id_b}")

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.conn.execute(
            """INSERT OR IGNORE INTO memory_relations
               (memory_id_a, memory_id_b, relation_type, description, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (memory_id_a, memory_id_b, relation_type, description, now),
        )

    def remove_relation(self, memory_id_a: str, memory_id_b: str, relation_type: str) -> None:
        """移除关联（调用方负责 commit）。"""
        self.conn.execute(
            """DELETE FROM memory_relations
               WHERE memory_id_a = ? AND memory_id_b = ? AND relation_type = ?""",
            (memory_id_a, memory_id_b, relation_type),
        )

    def list_relations(self, memory_id: str) -> list[dict]:
        """列出知识条目的所有关联。"""
        rows = self.conn.execute(
            """SELECT * FROM memory_relations
               WHERE memory_id_a = ? OR memory_id_b = ?
               ORDER BY created_at DESC""",
            (memory_id, memory_id),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "memory_id_a": r["memory_id_a"],
                "memory_id_b": r["memory_id_b"],
                "relation_type": r["relation_type"],
                "description": r["description"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ==================================================================
    # 工具方法
    # ==================================================================

    def _row_to_memory_item(self, row: sqlite3.Row) -> MemoryItem:
        """sqlite3.Row → MemoryItem dataclass（含标签加载）。"""
        memory_id = row["id"]
        tag_rows = self.conn.execute(
            "SELECT tag FROM memory_tags WHERE memory_id = ? ORDER BY id",
            (memory_id,),
        ).fetchall()
        tags = [r["tag"] for r in tag_rows]

        return MemoryItem(
            id=memory_id,
            project_id=row["project_id"],
            module=row["module"] or "",
            type=row["type"],
            title=row["title"],
            content=row["content"],
            content_hash=row["content_hash"],
            status=row["status"],
            index_status=row["index_status"] or "not_indexed",
            confidence=row["confidence"] if row["confidence"] is not None else 0.5,
            risk_level=row["risk_level"] or "low",
            scope=row["scope"] or "project",
            allowed_projects=json.loads(row["allowed_projects"]) if row["allowed_projects"] else [],
            denied_projects=json.loads(row["denied_projects"]) if row["denied_projects"] else [],
            source_type=row["source_type"] or "ai_inferred",
            source_task_id=row["source_task_id"],
            source_agent=row["source_agent"],
            source_evidence=json.loads(row["source_evidence"]) if row["source_evidence"] else {},
            source_file=row["source_file"],
            source_line=row["source_line"],
            tags=tags,
            parent_id=row["parent_id"],
            superseded_by=row["superseded_by"],
            created_by=row["created_by"],
            reviewed_by=row["reviewed_by"],
            review_comment=row["review_comment"],
            embedding_model=row["embedding_model"],
            vector_id=row["vector_id"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
            reviewed_at=row["reviewed_at"],
            expires_at=row["expires_at"],
        )

    @staticmethod
    def _item_to_json(item: Optional[MemoryItem]) -> str:
        """MemoryItem → JSON 字符串（用于 audit_log）。"""
        if item is None:
            return "null"
        return json.dumps(
            {
                "id": item.id,
                "project_id": item.project_id,
                "title": item.title,
                "type": item.type,
                "module": item.module,
                "status": item.status,
                "index_status": item.index_status,
                "confidence": item.confidence,
                "risk_level": item.risk_level,
                "scope": item.scope,
                "source_type": item.source_type,
                "source_file": item.source_file,
                "source_line": item.source_line,
            },
            ensure_ascii=False,
        )

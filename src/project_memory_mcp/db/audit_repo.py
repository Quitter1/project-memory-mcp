"""审计日志仓库。"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional


class AuditRepository:
    """审计日志数据访问层。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def log_action(
        self,
        action: str,
        project_id: Optional[str] = None,
        memory_id: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        actor: str = "system",
        reason: str = "",
        task_id: Optional[str] = None,
    ) -> int:
        """
        写入一条审计日志。

        参数：
        - action: 操作类型（memory_created, status_changed, scope_changed, memory_deprecated 等）
        - project_id: 关联项目 ID
        - memory_id: 关联知识 ID
        - old_value: 变更前的 JSON
        - new_value: 变更后的 JSON
        - actor: 操作者标识
        - reason: 操作原因
        - task_id: 关联任务 ID
        返回：日志记录 ID
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cursor = self.conn.execute(
            """INSERT INTO audit_log (
                project_id, memory_id, action, old_value, new_value,
                actor, reason, task_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, memory_id, action, old_value, new_value, actor, reason, task_id, now),
        )
        return cursor.lastrowid or 0

    def list_by_memory_id(self, memory_id: str, limit: int = 50) -> list[dict]:
        """查询某条知识的所有审计日志。"""
        rows = self.conn.execute(
            "SELECT * FROM audit_log WHERE memory_id = ? ORDER BY created_at DESC LIMIT ?",
            (memory_id, limit),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_by_project_id(self, project_id: str, limit: int = 100) -> list[dict]:
        """查询某个项目的所有审计日志。"""
        rows = self.conn.execute(
            "SELECT * FROM audit_log WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """sqlite3.Row → dict。"""
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "memory_id": row["memory_id"],
            "action": row["action"],
            "old_value": json.loads(row["old_value"]) if row["old_value"] else None,
            "new_value": json.loads(row["new_value"]) if row["new_value"] else None,
            "actor": row["actor"],
            "reason": row["reason"],
            "task_id": row["task_id"],
            "created_at": row["created_at"],
        }

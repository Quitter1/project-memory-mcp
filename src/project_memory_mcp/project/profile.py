"""项目画像构建 — 统计信息聚合（供 get_project_profile 工具使用）。"""

from typing import Optional

from ..db.memory_repo import MemoryRepository
from ..db.project_repo import ProjectRepository
from ..models.project import Project


class ProjectProfileBuilder:
    """构建项目画像。"""

    def __init__(self, memory_repo: MemoryRepository, project_repo: ProjectRepository):
        self.memory_repo = memory_repo
        self.project_repo = project_repo

    def build(self, project_id: str) -> Optional[dict]:
        """
        构建项目画像，包含：
        - 项目基本信息
        - 知识统计（总数、按状态、按类型）
        - 最近更新时间
        """
        project = self.project_repo.get_by_id(project_id)
        if project is None:
            return None

        # 统计
        all_memories = self.memory_repo.list_memories(project_id, limit=10000)
        total = len(all_memories)

        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for m in all_memories:
            by_status[m.status] = by_status.get(m.status, 0) + 1
            by_type[m.type] = by_type.get(m.type, 0) + 1

        # 最近更新时间
        last_updated = ""
        if all_memories:
            last_updated = max(m.updated_at for m in all_memories if m.updated_at)

        return {
            "project": {
                "id": project.id,
                "name": project.name,
                "slug": project.slug,
                "description": project.description,
                "status": project.status,
                "tech_stack": project.tech_stack,
                "root_paths": project.root_paths,
                "aliases": project.aliases,
                "knowledge_policy": {
                    "auto_approve_threshold": project.auto_approve_threshold,
                    "max_candidate_per_task": project.max_candidate_per_task,
                },
                "review_policy": project.review_policy,
            },
            "stats": {
                "total_memories": total,
                "by_status": by_status,
                "by_type": by_type,
                "last_updated": last_updated,
            },
        }

"""项目管理 — CRUD + sync_projects（YAML → SQLite）。"""

from typing import Optional

from ..config.loader import ConfigLoader
from ..config.schema import ProjectConfig
from ..db.project_repo import ProjectRepository
from ..models.project import Project


class ProjectManager:
    """项目经理。"""

    def __init__(self, project_repo: ProjectRepository, config_loader: ConfigLoader):
        self.project_repo = project_repo
        self.config_loader = config_loader

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_projects(self, status_filter: str = "all") -> list[Project]:
        """列出项目。"""
        return self.project_repo.list_projects(status_filter)

    def list_active_projects(self) -> list[Project]:
        """列出活跃项目。"""
        return self.project_repo.list_active()

    def get_project(self, project_id: str) -> Optional[Project]:
        """获取单个项目。"""
        return self.project_repo.get_by_id(project_id)

    # ------------------------------------------------------------------
    # 同步
    # ------------------------------------------------------------------

    def sync_from_yaml(
        self,
        actor: str = "sync_projects",
    ) -> dict:
        """
        从 projects.yml 同步项目配置到 SQLite。

        规则：
        - YAML 是权威源，覆盖 SQLite
        - 不删除已在 SQLite 中但不在 YAML 中的项目（手动保留）
        - 计算 yaml_hash 用于后续变更检测
        - 写 audit_log
        """
        yaml_projects = self.config_loader.load_all_projects()
        yaml_hash = self.config_loader.compute_yaml_hash()
        created = 0
        updated = 0

        for yp in yaml_projects:
            existing = self.project_repo.get_by_id(yp.id)
            project_model = self._to_db_model(yp, yaml_hash)
            self.project_repo.upsert_project(
                project_model,
                actor=actor,
                reason=f"sync from projects.yml (hash={yaml_hash[:12]})",
            )
            if existing is None:
                created += 1
            else:
                updated += 1

        return {
            "total_in_yaml": len(yaml_projects),
            "created": created,
            "updated": updated,
            "yaml_hash": yaml_hash,
        }

    def update_status(
        self,
        project_id: str,
        new_status: str,
        actor: str = "system",
        reason: str = "",
    ) -> Optional[Project]:
        """更新项目状态。"""
        return self.project_repo.update_status(project_id, new_status, actor=actor, reason=reason)

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _to_db_model(config: ProjectConfig, yaml_hash: str) -> Project:
        """ProjectConfig → Project (DB model)。"""
        return Project(
            id=config.id,
            name=config.name,
            slug=config.slug,
            description=config.description,
            status=config.status,
            root_paths=config.recognition.root_paths,
            path_patterns=config.recognition.path_patterns,
            aliases=config.recognition.aliases,
            tech_stack=config.recognition.tech_stack_keywords,
            module_keywords=config.recognition.module_keywords,
            default_confidence=config.knowledge_policy.default_confidence,
            auto_approve_threshold=config.knowledge_policy.auto_approve_threshold,
            max_candidate_per_task=config.knowledge_policy.max_candidate_per_task,
            retention_days=config.knowledge_policy.retention_days,
            review_policy={
                "allow_ai_auto_approve": config.review_policy.allow_ai_auto_approve,
                "forbidden_auto_types": config.review_policy.forbidden_auto_types,
                "risk_threshold_for_review": config.review_policy.risk_threshold_for_review,
                "require_review_if_conflict": config.review_policy.require_review_if_conflict,
            },
            metadata=config.metadata,
            superseded_by=config.superseded_by,
            merged_into=config.merged_into,
            yaml_hash=yaml_hash,
        )

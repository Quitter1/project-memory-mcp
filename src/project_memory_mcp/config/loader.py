"""配置加载器 — YAML 加载、校验、defaults 合并、sync_projects。"""

import hashlib
import yaml
from pathlib import Path
from typing import Optional

from .schema import (
    ProjectConfig,
    RecognitionConfig,
    KnowledgePolicyConfig,
    ReviewPolicyConfig,
    ServerConfig,
    MemoryPolicyConfig,
)

# 项目必填字段
REQUIRED_PROJECT_FIELDS = {"name", "slug"}


class ConfigError(Exception):
    """配置错误。"""
    pass


class ConfigLoader:
    """加载并校验 projects.yml、server.yml、memory-policy.yml。"""

    def __init__(self, config_dir: str):
        self.config_dir = Path(config_dir)

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def load_projects_config(self) -> dict:
        """加载 projects.yml 原始数据。"""
        path = self.config_dir / "projects.yml"
        if not path.exists():
            raise ConfigError(f"找不到配置文件: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def load_all_projects(self) -> list[ProjectConfig]:
        """
        加载并解析所有项目配置（含 defaults 合并）。

        返回 ProjectConfig 列表。
        """
        raw = self.load_projects_config()
        defaults = raw.get("defaults", {})
        sharing_rules = raw.get("sharing_rules", {})
        projects_raw = raw.get("projects", {})

        if not projects_raw:
            raise ConfigError("projects.yml 中没有定义任何项目 (projects 段为空)")

        # 校验 defaults
        self._validate_defaults(defaults)

        result: list[ProjectConfig] = []
        for project_id, data in projects_raw.items():
            try:
                project = self._parse_project(project_id, data, defaults)
                result.append(project)
            except ConfigError as e:
                raise ConfigError(f"项目 [{project_id}] 解析失败: {e}") from e

        return result

    def get_project(self, project_id: str) -> Optional[ProjectConfig]:
        """根据 ID 获取单个项目配置。"""
        projects = self.load_all_projects()
        for p in projects:
            if p.id == project_id:
                return p
        return None

    def list_active_projects(self) -> list[ProjectConfig]:
        """获取所有 active 项目。"""
        return [p for p in self.load_all_projects() if p.status == "active"]

    def compute_yaml_hash(self) -> str:
        """计算 projects.yml 的内容哈希（用于检测配置变更）。"""
        path = self.config_dir / "projects.yml"
        if not path.exists():
            return ""
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()

    def load_server_config(self) -> ServerConfig:
        """加载 server.yml。"""
        path = self.config_dir / "server.yml"
        if not path.exists():
            return ServerConfig()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        server_data = data.get("server", {})
        return ServerConfig(
            name=server_data.get("name", "project-memory-mcp"),
            version=server_data.get("version", "0.1.0"),
            log_level=server_data.get("log_level", "INFO"),
        )

    def load_memory_policy(self) -> MemoryPolicyConfig:
        """加载 memory-policy.yml。"""
        path = self.config_dir / "memory-policy.yml"
        if not path.exists():
            return MemoryPolicyConfig()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        detection = data.get("sensitive_detection", {})
        auto = data.get("auto_approval", {})
        return MemoryPolicyConfig(
            blocked_rules=detection.get("blocked", []),
            warning_rules=detection.get("warning", []),
            auto_approval_conditions=auto.get("conditions", []),
        )

    # ------------------------------------------------------------------
    # 内部解析
    # ------------------------------------------------------------------

    def _parse_project(
        self,
        project_id: str,
        data: dict,
        defaults: dict,
    ) -> ProjectConfig:
        """解析单个项目配置，合并 defaults。"""
        # 必填字段校验
        for field in REQUIRED_PROJECT_FIELDS:
            if field not in data or not data[field]:
                raise ConfigError(f"缺少必填字段: {field}")

        # defaults 合并
        default_kp = defaults.get("knowledge_policy", {})
        default_rp = defaults.get("review_policy", {})

        # 识别配置
        rec_raw = data.get("recognition", {})
        recognition = RecognitionConfig(
            root_paths=rec_raw.get("root_paths", []),
            path_patterns=rec_raw.get("path_patterns", []),
            aliases=rec_raw.get("aliases", []),
            tech_stack_keywords=rec_raw.get("tech_stack_keywords", []),
            module_keywords=rec_raw.get("module_keywords", []),
        )

        # 知识策略
        kp_raw = data.get("knowledge_policy", {})
        knowledge_policy = KnowledgePolicyConfig(
            default_confidence=kp_raw.get("default_confidence", default_kp.get("default_confidence", 0.5)),
            auto_approve_threshold=kp_raw.get("auto_approve_threshold", default_kp.get("auto_approve_threshold", -1)),
            max_candidate_per_task=kp_raw.get("max_candidate_per_task", default_kp.get("max_candidate_per_task", 20)),
            retention_days=kp_raw.get("retention_days", default_kp.get("retention_days", 365)),
            forbidden_content_patterns=kp_raw.get("forbidden_content_patterns", []),
        )

        # 审核策略
        rp_raw = data.get("review_policy", {})
        review_policy = ReviewPolicyConfig(
            allow_ai_auto_approve=rp_raw.get("allow_ai_auto_approve", default_rp.get("allow_ai_auto_approve", False)),
            forbidden_auto_types=rp_raw.get("forbidden_auto_types", default_rp.get("forbidden_auto_types", [])),
            risk_threshold_for_review=rp_raw.get("risk_threshold_for_review", default_rp.get("risk_threshold_for_review", "medium")),
            require_review_if_conflict=rp_raw.get("require_review_if_conflict", default_rp.get("require_review_if_conflict", True)),
        )

        # 校验字段类型和值
        self._validate_project(project_id, data)

        return ProjectConfig(
            id=project_id,
            name=data.get("name", ""),
            slug=data.get("slug", ""),
            description=data.get("description", ""),
            status=data.get("status", "active"),
            recognition=recognition,
            knowledge_policy=knowledge_policy,
            review_policy=review_policy,
            metadata=data.get("metadata", {}),
            superseded_by=data.get("superseded_by"),
            merged_into=data.get("merged_into"),
        )

    # ------------------------------------------------------------------
    # 类型判断 helper（Python 中 bool 是 int 子类，需显式排除）
    # ------------------------------------------------------------------

    @staticmethod
    def _is_number(val) -> bool:
        """是否为数字（排除 bool）。"""
        return isinstance(val, (int, float)) and not isinstance(val, bool)

    @staticmethod
    def _is_integer(val) -> bool:
        """是否为整数（排除 bool）。"""
        return isinstance(val, int) and not isinstance(val, bool)

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------

    def _validate_defaults(self, defaults: dict) -> None:
        """校验 defaults 中各字段的类型合法性。"""
        VALID_RISK = {"low", "medium", "high", "critical"}

        kp = defaults.get("knowledge_policy", {})
        if "default_confidence" in kp and not self._is_number(kp["default_confidence"]):
            raise ConfigError(
                f"defaults.knowledge_policy.default_confidence 必须是数字，实际: {type(kp['default_confidence']).__name__}"
            )
        if "auto_approve_threshold" in kp and not self._is_number(kp["auto_approve_threshold"]):
            raise ConfigError(
                f"defaults.knowledge_policy.auto_approve_threshold 必须是数字，实际: {type(kp['auto_approve_threshold']).__name__}"
            )
        if "max_candidate_per_task" in kp and not self._is_integer(kp["max_candidate_per_task"]):
            raise ConfigError(
                f"defaults.knowledge_policy.max_candidate_per_task 必须是整数，实际: {type(kp['max_candidate_per_task']).__name__}"
            )
        if "retention_days" in kp and not self._is_integer(kp["retention_days"]):
            raise ConfigError(
                f"defaults.knowledge_policy.retention_days 必须是整数，实际: {type(kp['retention_days']).__name__}"
            )

        rp = defaults.get("review_policy", {})
        if "allow_ai_auto_approve" in rp and not isinstance(rp["allow_ai_auto_approve"], bool):
            raise ConfigError(
                f"defaults.review_policy.allow_ai_auto_approve 必须是 bool，实际: {type(rp['allow_ai_auto_approve']).__name__}"
            )
        if "forbidden_auto_types" in rp and not isinstance(rp["forbidden_auto_types"], list):
            raise ConfigError(
                f"defaults.review_policy.forbidden_auto_types 必须是 list，实际: {type(rp['forbidden_auto_types']).__name__}"
            )
        if "risk_threshold_for_review" in rp:
            risk_val = rp["risk_threshold_for_review"]
            if risk_val not in VALID_RISK:
                raise ConfigError(
                    f"defaults.review_policy.risk_threshold_for_review 非法: '{risk_val}'，允许值: {VALID_RISK}"
                )
        if "require_review_if_conflict" in rp and not isinstance(rp["require_review_if_conflict"], bool):
            raise ConfigError(
                f"defaults.review_policy.require_review_if_conflict 必须是 bool，实际: {type(rp['require_review_if_conflict']).__name__}"
            )

    def _validate_project(self, project_id: str, data: dict) -> None:
        """校验项目配置字段类型和值合法性。"""
        VALID_STATUSES = {"active", "archived", "disabled"}
        VALID_RISK = {"low", "medium", "high", "critical"}

        status = data.get("status", "active")
        if status not in VALID_STATUSES:
            raise ConfigError(
                f"project[{project_id}].status 非法: '{status}'，允许值: {VALID_STATUSES}"
            )

        rec = data.get("recognition", {})

        for field in ("root_paths", "path_patterns", "aliases",
                       "tech_stack_keywords", "module_keywords"):
            val = rec.get(field, [])
            if not isinstance(val, list):
                raise ConfigError(
                    f"project[{project_id}].recognition.{field} 必须是 list，实际: {type(val).__name__}"
                )

        kp = data.get("knowledge_policy", {})

        if "default_confidence" in kp and not self._is_number(kp["default_confidence"]):
            raise ConfigError(
                f"project[{project_id}].knowledge_policy.default_confidence 必须是数字，实际: {type(kp['default_confidence']).__name__}"
            )
        if "auto_approve_threshold" in kp and not self._is_number(kp["auto_approve_threshold"]):
            raise ConfigError(
                f"project[{project_id}].knowledge_policy.auto_approve_threshold 必须是数字，实际: {type(kp['auto_approve_threshold']).__name__}"
            )
        if "max_candidate_per_task" in kp and not self._is_integer(kp["max_candidate_per_task"]):
            raise ConfigError(
                f"project[{project_id}].knowledge_policy.max_candidate_per_task 必须是整数，实际: {type(kp['max_candidate_per_task']).__name__}"
            )
        if "retention_days" in kp and not self._is_integer(kp["retention_days"]):
            raise ConfigError(
                f"project[{project_id}].knowledge_policy.retention_days 必须是整数，实际: {type(kp['retention_days']).__name__}"
            )

        rp = data.get("review_policy", {})

        if "allow_ai_auto_approve" in rp and not isinstance(rp["allow_ai_auto_approve"], bool):
            raise ConfigError(
                f"project[{project_id}].review_policy.allow_ai_auto_approve 必须是 bool，实际: {type(rp['allow_ai_auto_approve']).__name__}"
            )
        if "forbidden_auto_types" in rp and not isinstance(rp["forbidden_auto_types"], list):
            raise ConfigError(
                f"project[{project_id}].review_policy.forbidden_auto_types 必须是 list，实际: {type(rp['forbidden_auto_types']).__name__}"
            )
        if "risk_threshold_for_review" in rp:
            risk_val = rp["risk_threshold_for_review"]
            if risk_val not in VALID_RISK:
                raise ConfigError(
                    f"project[{project_id}].review_policy.risk_threshold_for_review 非法: '{risk_val}'，允许值: {VALID_RISK}"
                )
        if "require_review_if_conflict" in rp and not isinstance(rp["require_review_if_conflict"], bool):
            raise ConfigError(
                f"project[{project_id}].review_policy.require_review_if_conflict 必须是 bool，实际: {type(rp['require_review_if_conflict']).__name__}"
            )

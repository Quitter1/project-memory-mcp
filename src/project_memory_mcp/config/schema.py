"""配置 dataclass 定义。"""

# TODO: 阶段 2 实现


from dataclasses import dataclass, field


@dataclass
class RecognitionConfig:
    root_paths: list[str] = field(default_factory=list)
    path_patterns: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    tech_stack_keywords: list[str] = field(default_factory=list)
    module_keywords: list[str] = field(default_factory=list)


@dataclass
class KnowledgePolicyConfig:
    default_confidence: float = 0.5
    auto_approve_threshold: float = -1
    max_candidate_per_task: int = 20
    retention_days: int = 365
    forbidden_content_patterns: list[str] = field(default_factory=list)


@dataclass
class ReviewPolicyConfig:
    allow_ai_auto_approve: bool = False
    forbidden_auto_types: list[str] = field(default_factory=list)
    risk_threshold_for_review: str = "medium"
    require_review_if_conflict: bool = True


@dataclass
class ProjectConfig:
    id: str = ""
    name: str = ""
    slug: str = ""
    description: str = ""
    status: str = "active"
    recognition: RecognitionConfig = field(default_factory=RecognitionConfig)
    knowledge_policy: KnowledgePolicyConfig = field(default_factory=KnowledgePolicyConfig)
    review_policy: ReviewPolicyConfig = field(default_factory=ReviewPolicyConfig)
    metadata: dict = field(default_factory=dict)
    superseded_by: str | None = None
    merged_into: str | None = None


@dataclass
class ServerConfig:
    name: str = "project-memory-mcp"
    version: str = "0.1.0"
    log_level: str = "INFO"


@dataclass
class MemoryPolicyConfig:
    blocked_rules: list[dict] = field(default_factory=list)
    warning_rules: list[dict] = field(default_factory=list)
    auto_approval_conditions: list[str] = field(default_factory=list)

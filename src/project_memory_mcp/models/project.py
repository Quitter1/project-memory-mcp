"""Project 数据模型。"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Project:
    """项目模型 — SQLite 运行时缓存，配置源为 projects.yml。"""
    id: str = ""
    name: str = ""
    slug: str = ""
    description: str = ""
    status: str = "active"

    # 识别配置
    root_paths: list[str] = field(default_factory=list)
    path_patterns: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    module_keywords: list[str] = field(default_factory=list)

    # 知识策略
    default_confidence: float = 0.5
    auto_approve_threshold: float = -1
    max_candidate_per_task: int = 20
    retention_days: int = 365

    # 审核策略
    review_policy: dict = field(default_factory=dict)

    # 迁移
    superseded_by: Optional[str] = None
    merged_into: Optional[str] = None

    # 配置同步
    yaml_hash: str = ""

    # 扩展
    metadata: dict = field(default_factory=dict)

    # 时间
    created_at: str = ""
    updated_at: str = ""

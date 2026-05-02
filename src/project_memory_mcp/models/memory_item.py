"""MemoryItem 数据模型。"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MemoryItem:
    """知识条目主模型。"""
    id: str = ""
    project_id: str = ""

    # 内容
    module: str = ""
    type: str = "other"
    title: str = ""
    content: str = ""
    content_hash: str = ""

    # 双状态
    status: str = "candidate"          # governance status
    index_status: str = "not_indexed"  # vector index status
    confidence: float = 0.5

    # 风险
    risk_level: str = "low"

    # 可见范围
    scope: str = "project"
    allowed_projects: list[str] = field(default_factory=list)
    denied_projects: list[str] = field(default_factory=list)

    # 来源
    source_type: str = "ai_inferred"
    source_task_id: Optional[str] = None
    source_agent: Optional[str] = None

    # 来源证据
    source_evidence: dict = field(default_factory=dict)
    source_file: Optional[str] = None
    source_line: Optional[int] = None

    # 标签
    tags: list[str] = field(default_factory=list)

    # 关系
    parent_id: Optional[str] = None
    superseded_by: Optional[str] = None

    # 审计
    created_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    review_comment: Optional[str] = None

    # 向量
    embedding_model: Optional[str] = None
    vector_id: Optional[str] = None

    # 时间
    created_at: str = ""
    updated_at: str = ""
    reviewed_at: Optional[str] = None
    expires_at: Optional[str] = None

    # 扩展
    metadata: dict = field(default_factory=dict)

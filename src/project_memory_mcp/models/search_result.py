"""SearchResult 数据模型。"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchResult:
    """单条搜索结果。"""
    id: str = ""
    title: str = ""
    content: str = ""
    type: str = ""
    module: str = ""
    scope: str = "project"
    confidence: float = 0.0
    risk_level: str = "low"
    tags: list[str] = field(default_factory=list)
    source_evidence: dict = field(default_factory=dict)
    match_type: str = ""            # keyword | semantic | hybrid
    relevance_score: float = 0.0
    from_project: Optional[str] = None  # shared/global 知识的来源项目


@dataclass
class SearchResultSet:
    """搜索结果集。"""
    query: str = ""
    project_id: str = ""
    project_resolved: bool = False
    context_pack: dict = field(default_factory=dict)
    total_found: int = 0
    search_method: str = "keyword"
    fallback_activated: bool = False

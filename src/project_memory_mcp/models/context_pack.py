"""ContextPack 输出格式 — search_project_context 的标准返回结构。"""

from dataclasses import dataclass, field


@dataclass
class ContextPackItem:
    """context_pack 中的单条知识。"""
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
    match_type: str = ""
    relevance_score: float = 0.0
    from_project: str = ""


@dataclass
class ContextPack:
    """搜索结果的 context_pack 输出格式。"""
    summary: str = ""
    project_context: list[ContextPackItem] = field(default_factory=list)
    shared_context: list[ContextPackItem] = field(default_factory=list)
    global_context: list[ContextPackItem] = field(default_factory=list)

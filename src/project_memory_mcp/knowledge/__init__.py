"""知识治理模块 — 审核、去重、校验、生命周期。"""

from .governance import KnowledgeGovernance
from .validator import ContentValidator
from .deduplicator import Deduplicator
from .lifecycle import LifecycleManager
from .reviewer import RuleBasedReviewer

__all__ = [
    "KnowledgeGovernance",
    "ContentValidator",
    "Deduplicator",
    "LifecycleManager",
    "RuleBasedReviewer",
]

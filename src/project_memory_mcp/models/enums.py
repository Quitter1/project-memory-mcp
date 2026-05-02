"""枚举定义：状态、scope、类型、风险等级等。"""

import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    # Python 3.10 兼容
    from enum import Enum

    class StrEnum(str, Enum):
        """Python 3.10 兼容的 StrEnum 实现。"""
        pass


class KnowledgeStatus(StrEnum):
    """知识治理状态。"""
    CANDIDATE = "candidate"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    CONFLICT = "conflict"


class IndexStatus(StrEnum):
    """向量索引状态。"""
    NOT_INDEXED = "not_indexed"
    INDEXED = "indexed"
    INDEX_FAILED = "index_failed"
    STALE = "stale"


class ProjectStatus(StrEnum):
    """项目状态。"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DISABLED = "disabled"


class Scope(StrEnum):
    """知识可见范围。"""
    PROJECT = "project"
    SHARED = "shared"
    GLOBAL = "global"


class RiskLevel(StrEnum):
    """知识风险等级。"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SourceType(StrEnum):
    """知识来源类型。"""
    AI_INFERRED = "ai_inferred"
    USER_CONFIRMED = "user_confirmed"
    CODE_VERIFIED = "code_verified"
    SQL_VERIFIED = "sql_verified"
    IMPORTED_DOC = "imported_doc"
    MANUAL_INPUT = "manual_input"
    TASK_SUMMARY = "task_summary"


class KnowledgeType(StrEnum):
    """知识类型。"""
    ARCHITECTURE = "architecture"
    PATTERN = "pattern"
    API = "api"
    DATA_MODEL = "data_model"
    BUSINESS_RULE = "business_rule"
    CONFIGURATION = "configuration"
    WORKAROUND = "workaround"
    CONVENTION = "convention"
    DEPENDENCY = "dependency"
    SECURITY_CONFIG = "security_config"
    TEST_KNOWLEDGE = "test_knowledge"
    PITFALL = "pitfall"
    DECISION = "decision"
    OTHER = "other"


class TagCategory(StrEnum):
    """标签分类（支持按表名、字段名、文件名、类名检索）。"""
    GENERAL = "general"
    TABLE_NAME = "table_name"
    FIELD_NAME = "field_name"
    FILE_NAME = "file_name"
    CLASS_NAME = "class_name"
    FUNCTION_NAME = "function_name"
    MODULE_NAME = "module_name"
    API_PATH = "api_path"


class RelationType(StrEnum):
    """知识关联类型。"""
    RELATED_TO = "related_to"
    DEPENDS_ON = "depends_on"
    CONFLICTS_WITH = "conflicts_with"
    SUPERSEDES = "supersedes"
    DERIVED_FROM = "derived_from"
    DOCUMENTS = "documents"

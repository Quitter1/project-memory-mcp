"""项目识别与管理模块。"""

from .resolver import ProjectResolver, ResolveRequest, ResolveResult
from .manager import ProjectManager
from .profile import ProjectProfileBuilder

__all__ = [
    "ProjectResolver",
    "ResolveRequest",
    "ResolveResult",
    "ProjectManager",
    "ProjectProfileBuilder",
]

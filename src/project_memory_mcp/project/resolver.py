"""多策略项目识别器 — 按优先级逐级尝试匹配当前项目。"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ResolveRequest:
    """项目识别请求。"""
    project_id: str | None = None
    workspace_path: str | None = None
    changed_files: list[str] = field(default_factory=list)
    related_files: list[str] = field(default_factory=list)
    task_description: str | None = None
    allow_multiple: bool = False


@dataclass
class ResolveResult:
    """项目识别结果。"""
    resolved: bool
    project: dict | None = None
    match_method: str | None = None
    confidence: float = 0.0
    ambiguous: bool = False
    candidates: list[dict] = field(default_factory=list)
    error: str | None = None
    message: str = ""
    suggest_projects: list[dict] = field(default_factory=list)
    warning: str | None = None  # 例如显式指定了 archived 项目


class ProjectResolver:
    """
    多策略项目识别器。

    优先级：
    1. 显式 project_id → 直接查询
    2. workspace_path 前缀匹配 root_paths（跨平台路径标准化）
    3. changed_files / related_files 路径前缀匹配
    4. task_description 关键词打分（别名 +3, 技术栈 +2, 模块 +1, 阈值 5）
    5. 多匹配 → ambiguous
    6. 无匹配 → unable_to_resolve_project

    路径匹配规则：
    - Windows/Linux 路径统一
    - 大小写在 Windows 上不敏感
    - 多个 root_path 命中时选最长前缀
    - archived/disabled 项目默认不参与自动识别
    """

    # 打分权重
    SCORE_ALIAS = 3
    SCORE_TECH = 2
    SCORE_MODULE = 1
    MIN_SCORE_THRESHOLD = 3

    def __init__(self, project_repo=None, config_loader=None):
        """
        可用两种方式初始化：
        - project_repo: 从 SQLite 读取项目
        - config_loader: 从 YAML 读取项目（Phase 2 主要方式）
        """
        self.project_repo = project_repo
        self.config_loader = config_loader

    def _get_all_projects(self):
        """获取所有项目配置。优先用 config_loader，否则用 project_repo。"""
        if self.config_loader:
            return self.config_loader.load_all_projects()
        if self.project_repo:
            return self.project_repo.list_projects("all")  # type: ignore
        return []

    def _get_project_by_id(self, project_id: str):
        """按 ID 获取项目。"""
        if self.config_loader:
            return self.config_loader.get_project(project_id)
        if self.project_repo:
            return self.project_repo.get_by_id(project_id)  # type: ignore
        return None

    # ------------------------------------------------------------------
    # 兼容性 helper：同时支持 ProjectConfig 和 Project 模型
    # ------------------------------------------------------------------

    @staticmethod
    def _get_root_paths(project) -> list[str]:
        """获取 root_paths — 兼容 ProjectConfig 和 Project。"""
        if hasattr(project, "recognition"):
            return list(project.recognition.root_paths) if project.recognition else []
        return list(project.root_paths) if hasattr(project, "root_paths") else []

    @staticmethod
    def _get_aliases(project) -> list[str]:
        """获取 aliases — 兼容 ProjectConfig 和 Project。"""
        if hasattr(project, "recognition"):
            return list(project.recognition.aliases) if project.recognition else []
        return list(project.aliases) if hasattr(project, "aliases") else []

    @staticmethod
    def _get_tech_keywords(project) -> list[str]:
        """获取 tech_stack keywords — 兼容 ProjectConfig 和 Project。"""
        if hasattr(project, "recognition"):
            return list(project.recognition.tech_stack_keywords) if project.recognition else []
        return list(project.tech_stack) if hasattr(project, "tech_stack") else []

    @staticmethod
    def _get_module_keywords(project) -> list[str]:
        """获取 module_keywords — 兼容 ProjectConfig 和 Project。"""
        if hasattr(project, "recognition"):
            return list(project.recognition.module_keywords) if project.recognition else []
        return list(project.module_keywords) if hasattr(project, "module_keywords") else []

    @staticmethod
    def _get_project_status(project) -> str:
        """获取项目状态。"""
        return getattr(project, "status", "active")

    def _project_to_dict(self, project) -> dict:
        """ProjectConfig 或 Project → 字典（用于返回结果）。"""
        tech = self._get_tech_keywords(project)
        return {
            "id": getattr(project, "id", ""),
            "name": getattr(project, "name", ""),
            "slug": getattr(project, "slug", ""),
            "description": getattr(project, "description", "") if hasattr(project, "description") else "",
            "status": self._get_project_status(project),
            "tech_stack": tech,
            "aliases": self._get_aliases(project),
            "root_paths": self._get_root_paths(project),
            "auto_approve_threshold": getattr(project, "auto_approve_threshold", -1),
        }

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def resolve(self, request: ResolveRequest) -> ResolveResult:
        """
        执行多策略项目识别。

        Strategy 1: 显式 project_id
        Strategy 2: workspace_path 匹配
        Strategy 3: changed_files 匹配
        Strategy 4: task_description 关键词打分
        """
        # Strategy 1: 显式 project_id
        if request.project_id:
            return self._resolve_by_id(request.project_id)

        # Strategy 2: workspace_path
        if request.workspace_path:
            result = self._resolve_by_path(request.workspace_path)
            if result.resolved:
                return result  # 包括 ambiguous 结果，不往下掉

        # Strategy 3: file paths
        all_files = list(set(request.changed_files + request.related_files))
        if all_files:
            result = self._resolve_by_files(all_files)
            if result.resolved:
                return result  # 包括 ambiguous 结果，不往下掉

        # Strategy 4: task_description 弱匹配
        if request.task_description:
            result = self._resolve_by_description(request.task_description, request.allow_multiple)
            if result.resolved:
                return result

        # 失败
        return self._no_match_result()

    # ------------------------------------------------------------------
    # Strategy 1: 显式 ID
    # ------------------------------------------------------------------

    def _resolve_by_id(self, project_id: str) -> ResolveResult:
        """Strategy 1: 显式 project_id 查询。"""
        project = self._get_project_by_id(project_id)
        if project is None:
            active = self._get_active_summaries()
            return ResolveResult(
                resolved=False,
                error="project_not_found",
                message=f"项目 '{project_id}' 不存在",
                suggest_projects=active,
            )

        result = ResolveResult(
            resolved=True,
            project=self._project_to_dict(project),
            match_method="explicit_id",
            confidence=1.0,
        )

        status = self._get_project_status(project)
        if status != "active":
            result.warning = f"项目 '{project_id}' 状态为 {status}，已不活跃"

        return result

    # ------------------------------------------------------------------
    # Strategy 2: workspace_path
    # ------------------------------------------------------------------

    def _resolve_by_path(self, workspace_path: str) -> ResolveResult:
        """Strategy 2: workspace_path 匹配 root_paths。"""
        return self._match_paths([workspace_path], "workspace_path")

    # ------------------------------------------------------------------
    # Strategy 3: files
    # ------------------------------------------------------------------

    def _resolve_by_files(self, files: list[str]) -> ResolveResult:
        """Strategy 3: changed_files 匹配 root_paths。"""
        return self._match_paths(files, "changed_files")

    def _match_paths(self, paths: list[str], method: str) -> ResolveResult:
        """公共路径匹配逻辑。"""
        all_projects = self._get_all_projects()
        active = [p for p in all_projects if self._get_project_status(p) == "active"]

        scored: list[tuple[object, int, str]] = []
        for project in active:
            for root_path in self._get_root_paths(project):
                root_norm = self._normalize_path(root_path)
                for p in paths:
                    path_norm = self._normalize_path(p)
                    if path_norm.startswith(root_norm):
                        # 统计命中文件数
                        scored.append((project, len(root_norm), root_path))

        if not scored:
            return ResolveResult(resolved=False)

        # 选最长前缀（最精确匹配）
        scored.sort(key=lambda x: x[1], reverse=True)
        best_score = scored[0][1]
        top = [s for s in scored if s[1] == best_score]

        # 去重 project
        unique_projects: list[ProjectConfig] = []
        seen: set[str] = set()
        for proj, _, _ in top:
            if proj.id not in seen:
                unique_projects.append(proj)
                seen.add(proj.id)

        if len(unique_projects) > 1:
            return ResolveResult(
                resolved=True,
                ambiguous=True,
                candidates=[
                    {
                        "project_id": p.id,
                        "name": p.name,
                        "match_method": method,
                        "confidence": 0.9,
                    }
                    for p in unique_projects
                ],
                message=f"匹配到 {len(unique_projects)} 个项目，请显式指定 project_id",
            )

        p = unique_projects[0]
        return ResolveResult(
            resolved=True,
            project=self._project_to_dict(p),
            match_method=method,
            confidence=0.9,
        )

    # ------------------------------------------------------------------
    # Strategy 4: task_description 关键词打分
    # ------------------------------------------------------------------

    def _resolve_by_description(
        self,
        description: str,
        allow_multiple: bool = False,
    ) -> ResolveResult:
        """Strategy 4: 文本关键词打分。"""
        all_projects = self._get_all_projects()
        active = [p for p in all_projects if self._get_project_status(p) == "active"]
        desc_lower = description.lower()

        scored: list[tuple[object, int]] = []
        for project in active:
            score = 0

            # 别名
            for alias in self._get_aliases(project):
                if alias.lower() in desc_lower:
                    score += self.SCORE_ALIAS

            # 技术栈
            for kw in self._get_tech_keywords(project):
                if kw.lower() in desc_lower:
                    score += self.SCORE_TECH

            # 模块
            for kw in self._get_module_keywords(project):
                if kw.lower() in desc_lower:
                    score += self.SCORE_MODULE

            if score > 0:
                scored.append((project, score))

        if not scored:
            return ResolveResult(resolved=False)

        scored.sort(key=lambda x: x[1], reverse=True)
        best = scored[0][1]

        if best < self.MIN_SCORE_THRESHOLD:
            return ResolveResult(resolved=False)

        top = [s for s in scored if s[1] == best]

        if len(top) > 1 and not allow_multiple:
            return ResolveResult(
                resolved=True,
                ambiguous=True,
                candidates=[
                    {
                        "project_id": p.id,
                        "name": p.name,
                        "match_method": "task_description",
                        "confidence": min(best / (self.SCORE_ALIAS * 5), 1.0),
                    }
                    for p, s in top
                ],
                message=f"文本匹配到 {len(top)} 个项目，请显式指定 project_id",
            )

        p, s = top[0]
        return ResolveResult(
            resolved=True,
            project=self._project_to_dict(p),
            match_method="task_description",
            confidence=min(s / (self.SCORE_ALIAS * 5), 1.0),
        )

    # ------------------------------------------------------------------
    # 失败路径
    # ------------------------------------------------------------------

    def _no_match_result(self) -> ResolveResult:
        """无法识别项目时的返回。"""
        active = self._get_active_summaries()
        return ResolveResult(
            resolved=False,
            error="unable_to_resolve_project",
            message="请显式指定 project_id，或提供 workspace_path / changed_files / task_description",
            suggest_projects=active,
        )

    def _get_active_summaries(self) -> list[dict]:
        """获取 active 项目摘要列表。"""
        active = [p for p in self._get_all_projects() if self._get_project_status(p) == "active"]
        return [
            {
                "id": getattr(p, "id", ""),
                "name": getattr(p, "name", ""),
                "slug": getattr(p, "slug", ""),
                "tech_stack": self._get_tech_keywords(p)[:5],
            }
            for p in active
        ]

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_path(path: str) -> str:
        """
        路径标准化：统一分隔符。

        大小写规则：
        - Windows 盘符路径（D:/xxx, F:\\xxx）→ 总是小写
        - 当前系统是 Windows → 总是小写
        - Linux 纯路径 → 保持大小写敏感
        """
        p = path.replace("\\", "/").rstrip("/") + "/"
        if os.name == "nt" or ProjectResolver._is_windows_drive_path(path):
            p = p.lower()
        return p

    @staticmethod
    def _is_windows_drive_path(path: str) -> bool:
        """检测是否是 Windows 盘符路径（如 D:/xxx、F:\\yyy）。"""
        return len(path) >= 2 and path[1] == ":" and path[0].isalpha()

    # _project_to_dict 已改为实例方法（兼容 ProjectConfig 和 Project），见上方

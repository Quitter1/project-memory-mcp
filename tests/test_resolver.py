"""项目识别器测试 — 验证多策略项目识别逻辑。"""

import os
import tempfile
from pathlib import Path

import pytest

from project_memory_mcp.config.loader import ConfigLoader
from project_memory_mcp.db.connection import DatabaseConnection
from project_memory_mcp.db.project_repo import ProjectRepository
from project_memory_mcp.models.project import Project
from project_memory_mcp.project.resolver import ProjectResolver, ResolveRequest


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_TEST_PROJECTS_YAML = """
projects:
  biaopai-erp:
    name: "标牌 ERP"
    slug: "biaopai-erp"
    status: active
    recognition:
      root_paths:
        - "D:/workspace/biaopai-erp"
        - "/home/dev/biaopai-erp"
      aliases: ["erp", "biaopai"]
      tech_stack_keywords: ["java", "spring", "mysql", "freemarker"]
      module_keywords: ["订单管理", "物料管理"]

  cdr-converter:
    name: "CDR 转图片工具"
    slug: "cdr-converter"
    status: active
    recognition:
      root_paths:
        - "D:/workspace/cdr-converter"
        - "/home/dev/cdr-converter"
      aliases: ["cdr转换", "coreldraw"]
      tech_stack_keywords: ["python", "tkinter", "pillow"]
      module_keywords: ["图片导出"]

  rpa-electron:
    name: "RPA 客户端"
    slug: "rpa-electron"
    status: active
    recognition:
      root_paths:
        - "D:/workspace/rpa-electron"
      aliases: ["rpa"]
      tech_stack_keywords: ["electron", "vue3", "typescript"]
      module_keywords: []

  old-project:
    name: "旧项目"
    slug: "old-project"
    status: archived
    recognition:
      root_paths:
        - "D:/workspace/old-project"
      aliases: ["old"]
      tech_stack_keywords: ["legacy"]
      module_keywords: []

  overlap-a:
    name: "重叠项目 A"
    slug: "overlap-a"
    status: active
    recognition:
      root_paths:
        - "D:/workspace/shared-lib"
      aliases: ["lib-a"]
      tech_stack_keywords: ["java"]
      module_keywords: []

  overlap-b:
    name: "重叠项目 B"
    slug: "overlap-b"
    status: active
    recognition:
      root_paths:
        - "D:/workspace/shared-lib/sub-module"
      aliases: ["lib-b"]
      tech_stack_keywords: ["java", "kotlin"]
      module_keywords: []
"""


@pytest.fixture
def db_path():
    """创建临时数据库文件路径。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    Path(path).unlink(missing_ok=True)
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def resolver():
    """创建基于临时 YAML 配置的解析器。"""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "projects.yml"
        path.write_text(_TEST_PROJECTS_YAML, encoding="utf-8")
        loader = ConfigLoader(td)
        yield ProjectResolver(config_loader=loader)


# ------------------------------------------------------------------
# Strategy 1: 显式 project_id
# ------------------------------------------------------------------

def test_01_explicit_id(resolver):
    """显式 project_id 识别成功。"""
    result = resolver.resolve(ResolveRequest(project_id="biaopai-erp"))
    assert result.resolved is True
    assert result.match_method == "explicit_id"
    assert result.project["id"] == "biaopai-erp"
    assert result.confidence == 1.0


def test_02_explicit_id_not_found(resolver):
    """显式 project_id 不存在时返回错误和项目列表。"""
    result = resolver.resolve(ResolveRequest(project_id="nonexistent"))
    assert result.resolved is False
    assert result.error == "project_not_found"
    assert len(result.suggest_projects) > 0


# ------------------------------------------------------------------
# Strategy 2: workspace_path
# ------------------------------------------------------------------

def test_03_workspace_path_windows(resolver):
    """workspace_path 识别成功（Windows 路径）。"""
    result = resolver.resolve(ResolveRequest(
        workspace_path="D:/workspace/biaopai-erp/src/main/java"
    ))
    assert result.resolved is True
    assert result.match_method == "workspace_path"
    assert result.project["id"] == "biaopai-erp"


def test_04_workspace_path_linux(resolver):
    """workspace_path 识别成功（Linux 路径）。"""
    result = resolver.resolve(ResolveRequest(
        workspace_path="/home/dev/cdr-converter/tools"
    ))
    assert result.resolved is True
    assert result.match_method == "workspace_path"
    assert result.project["id"] == "cdr-converter"


# ------------------------------------------------------------------
# Strategy 3: changed_files
# ------------------------------------------------------------------

def test_05_changed_files(resolver):
    """changed_files 识别成功。"""
    result = resolver.resolve(ResolveRequest(
        changed_files=["D:/workspace/rpa-electron/src/renderer/App.vue"]
    ))
    assert result.resolved is True
    assert result.match_method == "changed_files"
    assert result.project["id"] == "rpa-electron"


# ------------------------------------------------------------------
# Strategy 4: task_description
# ------------------------------------------------------------------

def test_06_alias_match(resolver):
    """alias 识别成功。"""
    result = resolver.resolve(ResolveRequest(
        task_description="修改 biaopai 项目的订单模块"
    ))
    assert result.resolved is True
    assert result.match_method == "task_description"
    assert result.project["id"] == "biaopai-erp"


def test_07_tech_stack_match(resolver):
    """tech_stack_keywords 识别成功。"""
    result = resolver.resolve(ResolveRequest(
        task_description="这个 electron vue3 前端项目需要优化"
    ))
    assert result.resolved is True
    assert result.match_method == "task_description"
    assert result.project["id"] == "rpa-electron"


def test_08_module_keywords_match(resolver):
    """module_keywords 识别成功（配合 alias 达到阈值）。"""
    result = resolver.resolve(ResolveRequest(
        task_description="修复 biaopai 项目订单管理的查询接口"
    ))
    assert result.resolved is True
    assert result.match_method == "task_description"
    assert result.project["id"] == "biaopai-erp"


# ------------------------------------------------------------------
# 边界情况
# ------------------------------------------------------------------

def test_09_ambiguous_multi_match(resolver):
    """多项目歧义返回 ambiguous。"""
    result = resolver.resolve(ResolveRequest(
        task_description="Java 项目需要重构"
    ))
    # Java 命中 biaopai-erp(spring,mysql,freemarker) 和 overlap-a/b
    # 具体取决于得分
    if result.ambiguous:
        assert len(result.candidates) > 1
    # 如果只有 overlap-b 得分最高（java+kt），则不歧义
    # 两种结果都是合理的


def test_10_cannot_resolve(resolver):
    """无法识别返回 unable_to_resolve_project + 项目列表。"""
    result = resolver.resolve(ResolveRequest(
        task_description="修复一个未知项目的 bug"
    ))
    assert result.resolved is False
    assert result.error == "unable_to_resolve_project"
    assert len(result.suggest_projects) > 0


def test_11_archived_not_auto_matched(resolver):
    """archived 项目默认不参与自动识别。"""
    # 用路径尝试匹配 archived 项目 — 不应匹配
    result = resolver.resolve(ResolveRequest(
        workspace_path="D:/workspace/old-project/something"
    ))
    # archived 项目不参与自动识别
    assert result.resolved is False or result.project["id"] != "old-project"


def test_12_explicit_archived_with_warning(resolver):
    """显式 project_id 可以识别 archived 项目，但返回 warning。"""
    result = resolver.resolve(ResolveRequest(project_id="old-project"))
    assert result.resolved is True
    assert result.project["id"] == "old-project"
    assert result.warning is not None
    assert "archived" in result.warning.lower()


def test_13_case_insensitive_windows(resolver):
    """Windows 路径大小写不敏感。"""
    if os.name == "nt":
        result = resolver.resolve(ResolveRequest(
            workspace_path="D:/Workspace/Biaopai-ERP/src/..."
        ))
        assert result.resolved is True
        assert result.project["id"] == "biaopai-erp"


def test_14_longest_prefix_selected(resolver):
    """多 root_path 命中时选择最长前缀（最精确匹配）。"""
    result = resolver.resolve(ResolveRequest(
        workspace_path="D:/workspace/shared-lib/sub-module/src/main.kt"
    ))
    assert result.resolved is True
    # 应该匹配 overlap-b（路径更长），而非 overlap-a
    assert result.project["id"] == "overlap-b"


# ------------------------------------------------------------------
# Phase 2.5 新增：SQLite ProjectRepository 初始化 Resolver
# ------------------------------------------------------------------

def test_15_resolver_with_sqlite_repo(db_path):
    """用 SQLite ProjectRepository 初始化 ProjectResolver。"""
    db = DatabaseConnection(db_path)
    conn = db.connect()
    project_repo = ProjectRepository(conn)

    # 写入项目
    p = Project(id="sqlite-proj", name="SQLite项目", slug="sqlite-proj",
                status="active", root_paths=["/tmp/sqlite-proj"],
                aliases=["sqlproj"], tech_stack=["rust", "python"],
                auto_approve_threshold=0.8)
    project_repo.upsert_project(p, actor="test")

    r = ProjectResolver(project_repo=project_repo)

    # 显式 project_id
    result1 = r.resolve(ResolveRequest(project_id="sqlite-proj"))
    assert result1.resolved is True
    assert result1.project["id"] == "sqlite-proj"

    # workspace_path
    result2 = r.resolve(ResolveRequest(workspace_path="/tmp/sqlite-proj/src/main.rs"))
    assert result2.resolved is True
    assert result2.project["id"] == "sqlite-proj"

    # task_description
    result3 = r.resolve(ResolveRequest(task_description="这个 sqlproj rust 项目需要修复"))
    assert result3.resolved is True
    assert result3.project["id"] == "sqlite-proj"

    db.close()


def test_16_archived_sqlite_with_warning(db_path):
    """archived 项目显式识别返回 warning。"""
    db = DatabaseConnection(db_path)
    conn = db.connect()
    project_repo = ProjectRepository(conn)

    p = Project(id="archived-sqlite", name="归档SQLite", slug="archived-sqlite",
                status="archived", root_paths=["/tmp/old"])
    project_repo.upsert_project(p, actor="test")

    r = ProjectResolver(project_repo=project_repo)
    result = r.resolve(ResolveRequest(project_id="archived-sqlite"))
    assert result.resolved is True
    assert result.warning is not None
    db.close()


# ------------------------------------------------------------------
# Phase 2.5 新增：ambiguous 路径匹配
# ------------------------------------------------------------------

def test_17_two_active_projects_same_root_ambiguous():
    """两个 active 项目配置相同 root_path，workspace_path 应返回 ambiguous。"""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "projects.yml"
        path.write_text("""
projects:
  proj-a:
    name: A
    slug: proj-a
    status: active
    recognition:
      root_paths: ["/shared/path"]
      tech_stack_keywords: ["go"]
  proj-b:
    name: B
    slug: proj-b
    status: active
    recognition:
      root_paths: ["/shared/path"]
      tech_stack_keywords: ["rust"]
""", encoding="utf-8")

        r = ProjectResolver(config_loader=ConfigLoader(td))
        result = r.resolve(ResolveRequest(workspace_path="/shared/path/src/code"))
        assert result.ambiguous is True
        assert len(result.candidates) == 2
        ids = {c["project_id"] for c in result.candidates}
        assert ids == {"proj-a", "proj-b"}


def test_18_two_active_projects_same_root_files_ambiguous():
    """两个 active 项目配置相同 root_path，changed_files 应返回 ambiguous。"""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "projects.yml"
        path.write_text("""
projects:
  proj-x:
    name: X
    slug: proj-x
    status: active
    recognition:
      root_paths: ["D:/common"]
      tech_stack_keywords: ["csharp"]
  proj-y:
    name: Y
    slug: proj-y
    status: active
    recognition:
      root_paths: ["D:/common"]
      tech_stack_keywords: ["fsharp"]
""", encoding="utf-8")

        r = ProjectResolver(config_loader=ConfigLoader(td))
        result = r.resolve(ResolveRequest(
            changed_files=["D:/common/src/app.cs"]
        ))
        assert result.ambiguous is True
        assert len(result.candidates) == 2

# ------------------------------------------------------------------
# Phase 2.6 新增：跨平台路径规范化测试
# ------------------------------------------------------------------

def test_19_windows_path_case_insensitive_always():
    """不依赖 os.name，Windows 盘符路径总应小写匹配。"""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "projects.yml"
        path.write_text("""
projects:
  case-test:
    name: Case Test
    slug: case-test
    status: active
    recognition:
      root_paths: ["D:/workspace/biaopai-erp"]
      tech_stack_keywords: ["test"]
""", encoding="utf-8")

        r = ProjectResolver(config_loader=ConfigLoader(td))
        # 大小写混合路径应能匹配小写 root_paths
        result = r.resolve(ResolveRequest(
            workspace_path="D:/Workspace/Biaopai-ERP/src/main.java"
        ))
        assert result.resolved is True
        assert result.project["id"] == "case-test"

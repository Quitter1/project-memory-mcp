"""检索模块测试 — 关键词搜索、隔离、过滤、context_pack。"""

import os
import tempfile
from pathlib import Path

import pytest

from project_memory_mcp.db.connection import DatabaseConnection
from project_memory_mcp.db.memory_repo import MemoryRepository
from project_memory_mcp.db.project_repo import ProjectRepository
from project_memory_mcp.models.project import Project
from project_memory_mcp.models.memory_item import MemoryItem
from project_memory_mcp.utils.hashing import compute_content_hash
from project_memory_mcp.retrieval.search import KnowledgeSearchService
from project_memory_mcp.retrieval.keyword_search import KeywordSearchService
from project_memory_mcp.retrieval.filter_builder import FilterBuilder


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    Path(path).unlink(missing_ok=True)
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def conn(db_path):
    db = DatabaseConnection(db_path)
    c = db.connect()
    yield c
    db.close()


@pytest.fixture
def project_repo(conn):
    return ProjectRepository(conn)


@pytest.fixture
def memory_repo(conn):
    return MemoryRepository(conn)


@pytest.fixture
def search_svc(conn):
    return KnowledgeSearchService(conn)


@pytest.fixture
def kw_svc(conn):
    return KeywordSearchService(conn)


# ------------------------------------------------------------------
# 种子数据
# ------------------------------------------------------------------

def _seed(project_repo, memory_repo):
    """创建多项目种子数据。"""
    # 项目 A
    pa = Project(id="proj-a", name="项目A", slug="proj-a", status="active",
                 root_paths=["/a"], tech_stack=["py"])
    project_repo.upsert_project(pa, actor="seed")

    # 项目 B
    pb = Project(id="proj-b", name="项目B", slug="proj-b", status="active",
                 root_paths=["/b"], tech_stack=["java"])
    project_repo.upsert_project(pb, actor="seed")

    # shared 虚拟项目（scope=shared/global 知识的宿主）
    ps = Project(id="shared", name="共享知识", slug="shared", status="active",
                 root_paths=[], tech_stack=[])
    project_repo.upsert_project(ps, actor="seed")

    def _mem(pid, title, content, mem_type="api", module="模块A", status="approved",
             scope="project", risk="low", confidence=0.9, tags=None,
             allowed_projects=None, denied_projects=None):
        item = MemoryItem(
            project_id=pid, module=module, type=mem_type, title=title, content=content,
            content_hash=compute_content_hash(content), status=status,
            index_status="not_indexed", confidence=confidence, risk_level=risk,
            scope=scope, source_type="manual_input", tags=tags or [],
            allowed_projects=allowed_projects or [], denied_projects=denied_projects or [],
        )
        return memory_repo.create_memory(item, actor="seed")

    # A 的 approved 知识
    _mem("proj-a", "A项目订单查询API", "订单查询接口返回分页数据", tags=["order", "query"])
    _mem("proj-a", "A项目物料管理", "物料管理模块设计文档", mem_type="architecture", tags=["material"])
    _mem("proj-a", "A项目配置说明", "数据库连接池配置", mem_type="configuration", module="基础设施")

    # A 的 candidate 知识
    _mem("proj-a", "A项目候选知识", "候选待审核内容", status="candidate")
    _mem("proj-a", "A项目待审核", "待审核知识", status="pending_review")

    # A 的 rejected/deprecated
    _mem("proj-a", "A项目已拒绝", "拒绝的知识", status="rejected")
    _mem("proj-a", "A项目已废弃", "废弃的知识", status="deprecated")

    # B 的 approved 知识
    _mem("proj-b", "B项目用户管理API", "用户管理接口文档", tags=["user", "api"])

    # shared 知识 — allowed proj-a
    _mem("shared", "共享Windows调试经验", "PowerShell常用命令", scope="shared",
         allowed_projects=["proj-a"], denied_projects=[])

    # shared 知识 — denied proj-a
    _mem("shared", "仅B可用的共享", "仅项目B可用的知识", scope="shared",
         allowed_projects=[], denied_projects=["proj-a"])

    # global 知识
    _mem("shared", "全局Python经验", "Python虚拟环境管理", scope="global",
         allowed_projects=[], denied_projects=[])


# ------------------------------------------------------------------
# 测试
# ------------------------------------------------------------------

class TestSearchIsolation:
    """检索隔离测试。"""

    def test_01_project_only_own_scope(self, project_repo, memory_repo, search_svc):
        """当前项目只搜到自己的 scope=project 知识。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "订单")
        project_items = result.context_pack["project_context"]
        titles = {i["title"] for i in project_items}
        assert "A项目订单查询API" in titles
        # 不应包含 B 的知识
        assert "B项目用户管理API" not in titles

    def test_02_not_other_project(self, project_repo, memory_repo, search_svc):
        """当前项目搜不到其他项目的 scope=project 知识。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "用户管理")
        project_items = result.context_pack["project_context"]
        assert len(project_items) == 0

    def test_03_shared_allowed_visible(self, project_repo, memory_repo, search_svc):
        """当前项目能搜到 scope=shared 且 allowed 的知识。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "调试 PowerShell")
        shared = result.context_pack["shared_context"]
        titles = {i["title"] for i in shared}
        assert "共享Windows调试经验" in titles

    def test_04_shared_denied_hidden(self, project_repo, memory_repo, search_svc):
        """当前项目搜不到 scope=shared 且 denied 的知识。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "仅B")
        shared = result.context_pack["shared_context"]
        titles = {i["title"] for i in shared}
        assert "仅B可用的共享" not in titles

    def test_05_global_visible(self, project_repo, memory_repo, search_svc):
        """当前项目能搜到 scope=global 知识。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "虚拟环境 Python")
        global_items = result.context_pack["global_context"]
        titles = {i["title"] for i in global_items}
        assert "全局Python经验" in titles


class TestSearchFiltering:
    """过滤测试。"""

    def test_06_default_approved_only(self, project_repo, memory_repo, search_svc):
        """默认只返回 approved。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "A项目")
        all_titles = (
            {i["title"] for i in result.context_pack["project_context"]}
            | {i["title"] for i in result.context_pack["shared_context"]}
            | {i["title"] for i in result.context_pack["global_context"]}
        )
        assert "A项目已拒绝" not in all_titles
        assert "A项目已废弃" not in all_titles

    def test_07_include_candidates(self, project_repo, memory_repo, search_svc):
        """include_candidates=true 时可返回 candidate/pending_review。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "A项目", include_candidates=True)
        titles = {i["title"] for i in result.context_pack["project_context"]}
        assert "A项目候选知识" in titles
        assert "A项目待审核" in titles

    def test_08_exclude_rejected_deprecated(self, project_repo, memory_repo, search_svc):
        """默认不返回 rejected/deprecated/superseded/conflict。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "A项目")
        all_ids = []
        for items in result.context_pack.values():
            if isinstance(items, list):
                all_ids.extend(i["id"] for i in items)
        # 检查没有 status=rejected/deprecated 的
        for mid in all_ids:
            mem = memory_repo.get_by_id(mid)
            assert mem.status not in ("rejected", "deprecated", "superseded", "conflict")

    def test_09_tag_search(self, project_repo, memory_repo, search_svc):
        """tag 命中可以被搜到。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "query")
        project_titles = {i["title"] for i in result.context_pack["project_context"]}
        assert "A项目订单查询API" in project_titles

    def test_10_module_filter(self, project_repo, memory_repo, search_svc):
        """module 过滤生效。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "A项目", modules=["基础设施"])
        project_titles = {i["title"] for i in result.context_pack["project_context"]}
        assert "A项目配置说明" in project_titles
        assert "A项目物料管理" not in project_titles

    def test_11_type_filter(self, project_repo, memory_repo, search_svc):
        """type 过滤生效。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "A项目", types=["architecture"])
        project_titles = {i["title"] for i in result.context_pack["project_context"]}
        assert "A项目物料管理" in project_titles
        assert "A项目订单查询API" not in project_titles

    def test_12_min_confidence(self, project_repo, memory_repo, search_svc):
        """min_confidence 过滤生效。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "A项目", min_confidence=0.95)
        project_titles = {i["title"] for i in result.context_pack["project_context"]}
        # 所有知识的 confidence=0.9，0.95 过滤掉全部
        assert len(project_titles) == 0

    def test_13_max_results(self, project_repo, memory_repo, search_svc):
        """max_results 生效。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "A项目", max_results=2)
        total = sum(
            len(result.context_pack[k])
            for k in ("project_context", "shared_context", "global_context")
            if isinstance(result.context_pack[k], list)
        )
        assert total <= 2

    def test_14_sql_injection_safe(self, project_repo, memory_repo, kw_svc):
        """查询参数使用参数化 SQL，包含引号的 query 不报错。"""
        _seed(project_repo, memory_repo)
        # 包含单引号和双引号的查询不应导致 SQL 错误
        results = kw_svc.search("proj-a", "test' OR 1=1 --")
        assert isinstance(results, list)
        results2 = kw_svc.search("proj-a", 'test" OR "1"="1')
        assert isinstance(results2, list)


class TestContextPack:
    """context_pack 格式测试。"""

    def test_15_context_pack_grouping(self, project_repo, memory_repo, search_svc):
        """context_pack 按 project/shared/global 分组。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "管理 用户")
        cp = result.context_pack
        assert "project_context" in cp
        assert "shared_context" in cp
        assert "global_context" in cp
        assert "summary" in cp
        assert isinstance(cp["project_context"], list)
        assert isinstance(cp["shared_context"], list)
        assert isinstance(cp["global_context"], list)

    def test_16_summary_correct(self, project_repo, memory_repo, search_svc):
        """context_pack summary 正确。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "管理")
        summary = result.context_pack["summary"]
        assert "项目知识" in summary
        assert "共享知识" in summary
        assert "全局知识" in summary

    def test_17_dedup(self, project_repo, memory_repo, search_svc):
        """重复结果会去重。"""
        _seed(project_repo, memory_repo)
        # 搜索两次同一个关键词，结果应无重复 id
        result = search_svc.search("proj-a", "A项目")
        all_ids = []
        for items in result.context_pack.values():
            if isinstance(items, list):
                all_ids.extend(i["id"] for i in items)
        assert len(all_ids) == len(set(all_ids))

    def test_18_empty_query(self, project_repo, memory_repo, search_svc):
        """空 query 返回最近知识，但仍遵守隔离规则。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "")
        project_items = result.context_pack["project_context"]
        # 不应包含 B 的知识
        for item in project_items:
            assert item.get("from_project", "proj-a") != "proj-b"


class TestFilterBuilder:
    """FilterBuilder 单元测试。"""

    def test_19_project_filter_sql(self):
        """project filter 生成参数化 SQL。"""
        clause = FilterBuilder.build_project_filter("my-project")
        assert "scope = 'project'" in clause.sql
        assert "project_id = ?" in clause.sql
        assert "my-project" in clause.params

    def test_20_shared_filter_allowed(self):
        """shared filter 检查 allowed_projects。"""
        clause = FilterBuilder.build_shared_filter("my-project")
        assert "scope = 'shared'" in clause.sql
        assert "allowed_projects" in clause.sql
        assert "denied_projects" in clause.sql

# ------------------------------------------------------------------
# Phase 3.1 新增：max_results 全局限制
# ------------------------------------------------------------------

class TestGlobalMaxResults:
    """全局 max_results 测试。"""

    def test_21_total_not_exceed_max_results(self, project_repo, memory_repo, search_svc):
        """project+shared+global 都命中时 max_results=2 总条数 <= 2。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "A项目", max_results=2)
        total = sum(
            len(result.context_pack[k])
            for k in ("project_context", "shared_context", "global_context")
            if isinstance(result.context_pack[k], list)
        )
        assert total <= 2

    def test_22_total_found_gte_total_returned(self, project_repo, memory_repo, search_svc):
        """total_found >= total_returned。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "A项目", max_results=1)
        assert result.total_found >= result.total_returned

    def test_23_total_returned_matches_context_pack(self, project_repo, memory_repo, search_svc):
        """total_returned == context_pack 三个分组数量之和。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "A项目", max_results=3)
        cp_total = sum(
            len(result.context_pack[k])
            for k in ("project_context", "shared_context", "global_context")
            if isinstance(result.context_pack[k], list)
        )
        assert result.total_returned == cp_total


class TestSourceEvidence:
    """source_evidence 测试。"""

    def test_24_source_evidence_in_search(self, project_repo, memory_repo, search_svc):
        """创建时写入 source_evidence，搜索后能读到。"""
        for pid in ['proj-a', 'shared']:
            pa = Project(id=pid, name=pid, slug=pid, status='active', root_paths=[], tech_stack=[])
            project_repo.upsert_project(pa, actor='seed')
        content = 'evi test'
        item = MemoryItem(
            project_id='proj-a', title='证据测试', content=content,
            content_hash=compute_content_hash(content), status='approved',
            scope='project', source_type='manual_input',
            source_evidence={'file': 'A.java', 'line': 3, 'reasoning': 'test'}
        )
        memory_repo.create_memory(item, actor='seed')
        result = search_svc.search("proj-a", "证据")
        items = result.context_pack["project_context"]
        assert len(items) >= 1
        assert items[0]["source_evidence"]["file"] == "A.java"
        assert items[0]["source_evidence"]["line"] == 3

    def test_25_source_file_line_to_evidence(self, project_repo, memory_repo, search_svc):
        """只有 source_file/source_line 字段时也能补进 source_evidence。"""
        for pid in ['proj-a', 'shared']:
            pa = Project(id=pid, name=pid, slug=pid, status='active', root_paths=[], tech_stack=[])
            project_repo.upsert_project(pa, actor='seed')
        content = 'file line test'
        item = MemoryItem(
            project_id='proj-a', title='文件行测试', content=content,
            content_hash=compute_content_hash(content), status='approved',
            scope='project', source_type='manual_input',
            source_file='B.java', source_line=42
        )
        memory_repo.create_memory(item, actor='seed')
        result = search_svc.search("proj-a", "文件行")
        items = result.context_pack["project_context"]
        assert len(items) >= 1
        assert items[0]["source_evidence"].get("file") == "B.java"
        assert items[0]["source_evidence"].get("line") == 42


class TestEmptyQueryFilters:
    """空 query 过滤测试。"""

    def test_26_empty_query_module_filter(self, project_repo, memory_repo, search_svc):
        """search(project_id, \"\", modules=[...]) 只返回该 module。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "", modules=["基础设施"])
        titles = {i["title"] for i in result.context_pack["project_context"]}
        assert "A项目配置说明" in titles
        assert "A项目物料管理" not in titles

    def test_27_empty_query_type_filter(self, project_repo, memory_repo, search_svc):
        """search(project_id, \"\", types=[...]) 只返回该 type。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "", types=["architecture"])
        titles = {i["title"] for i in result.context_pack["project_context"]}
        assert "A项目物料管理" in titles
        assert "A项目订单查询API" not in titles

    def test_28_empty_query_tag_filter(self, project_repo, memory_repo, search_svc):
        """search(project_id, \"\", tags=[...]) 只返回有该 tag 的知识。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "", tags=["order"])
        titles = {i["title"] for i in result.context_pack["project_context"]}
        assert "A项目订单查询API" in titles

    def test_29_empty_query_min_confidence(self, project_repo, memory_repo, search_svc):
        """search(project_id, \"\", min_confidence=0.95) 过滤低置信度。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "", min_confidence=0.95)
        titles = {i["title"] for i in result.context_pack["project_context"]}
        assert len(titles) == 0  # 所有知识 confidence=0.9


class TestInstrMembership:
    """instr JSON membership 测试。"""

    def test_30_instr_underscore_not_wildcard(self, project_repo, memory_repo, search_svc):
        """project_id 含 _ 时 instr 精确匹配，不被 LIKE 通配符误判。"""
        for pid in ['proj_a', 'shared']:
            pa = Project(id=pid, name=pid, slug=pid, status='active', root_paths=[], tech_stack=[])
            project_repo.upsert_project(pa, actor='seed')
        content = 'underscore membership test'
        item = MemoryItem(
            project_id='shared', title='下划线测试', content=content,
            content_hash=compute_content_hash(content), status='approved',
            scope='shared', source_type='manual_input',
            allowed_projects=['projXa'], denied_projects=[]
        )
        memory_repo.create_memory(item, actor='seed')
        result = search_svc.search("proj_a", "下划线")
        shared_titles = {i["title"] for i in result.context_pack["shared_context"]}
        assert "下划线测试" not in shared_titles

    def test_31_instr_exact_match(self, project_repo, memory_repo, search_svc):
        """shared allowed 精确匹配 project_id。"""
        for pid in ['proj_a', 'shared']:
            pa = Project(id=pid, name=pid, slug=pid, status='active', root_paths=[], tech_stack=[])
            project_repo.upsert_project(pa, actor='seed')
        content = 'exact match test'
        item = MemoryItem(
            project_id='shared', title='精确匹配测试', content=content,
            content_hash=compute_content_hash(content), status='approved',
            scope='shared', source_type='manual_input',
            allowed_projects=['proj_a'], denied_projects=[]
        )
        memory_repo.create_memory(item, actor='seed')
        result = search_svc.search("proj_a", "精确匹配")
        shared_titles = {i["title"] for i in result.context_pack["shared_context"]}
        assert "精确匹配测试" in shared_titles


class TestScopeNotPreempted:
    """shared/global 不被 project 提前挤掉。"""

    def test_32_shared_still_visible(self, project_repo, memory_repo, search_svc):
        """project 命中很多但 shared 仍有机会进入 merged。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "Windows PowerShell 调试")
        shared_titles = {i["title"] for i in result.context_pack["shared_context"]}
        assert "共享Windows调试经验" in shared_titles

    def test_33_global_still_visible_under_limit(self, project_repo, memory_repo, search_svc):
        """max_results 较小但不影响 global 可见性。"""
        _seed(project_repo, memory_repo)
        result = search_svc.search("proj-a", "Python 虚拟环境")
        global_titles = {i["title"] for i in result.context_pack["global_context"]}
        assert "全局Python经验" in global_titles

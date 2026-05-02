"""MemoryRepository + ProjectRepository + AuditRepository 集成测试。"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from project_memory_mcp.db.connection import DatabaseConnection
from project_memory_mcp.db.memory_repo import MemoryRepository
from project_memory_mcp.db.project_repo import ProjectRepository
from project_memory_mcp.db.audit_repo import AuditRepository
from project_memory_mcp.models.project import Project
from project_memory_mcp.models.memory_item import MemoryItem
from project_memory_mcp.utils.hashing import compute_content_hash


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def db_path():
    """创建临时数据库文件路径。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    Path(path).unlink(missing_ok=True)
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def conn(db_path) -> sqlite3.Connection:
    """创建已迁移的数据库连接。"""
    db = DatabaseConnection(db_path)
    c = db.connect()
    yield c
    db.close()


@pytest.fixture
def project_repo(conn) -> ProjectRepository:
    return ProjectRepository(conn)


@pytest.fixture
def memory_repo(conn) -> MemoryRepository:
    return MemoryRepository(conn)


@pytest.fixture
def audit_repo(conn) -> AuditRepository:
    return AuditRepository(conn)


@pytest.fixture
def sample_project(project_repo) -> Project:
    """创建测试项目。"""
    p = Project(
        id="test-project",
        name="测试项目",
        slug="test-project",
        description="用于测试的项目",
        status="active",
        root_paths=["D:/workspace/test"],
        aliases=["test", "测试"],
        tech_stack=["Python", "SQLite"],
        auto_approve_threshold=0.9,
        review_policy={"allow_ai_auto_approve": True},
    )
    return project_repo.upsert_project(p, actor="test_runner")


@pytest.fixture
def sample_memory(memory_repo, sample_project) -> MemoryItem:
    """创建测试知识条目。"""
    content = "这是一条测试知识：订单查询接口需要添加 @Transactional 注解"
    item = MemoryItem(
        project_id=sample_project.id,
        module="订单管理",
        type="api",
        title="订单查询接口事务注解",
        content=content,
        content_hash=compute_content_hash(content),
        status="candidate",
        confidence=0.7,
        risk_level="low",
        scope="project",
        source_type="ai_inferred",
        source_file="OrderController.java",
        source_line=45,
        source_evidence={"reasoning": "发现缺少事务注解"},
        tags=["order", "transaction", "spring"],
    )
    return memory_repo.create_memory(item, actor="test_runner", reason="测试创建")


# ------------------------------------------------------------------
# 测试：Project CRUD
# ------------------------------------------------------------------

def test_01_create_project(project_repo, sample_project):
    """创建 project 成功。"""
    assert sample_project.id == "test-project"
    assert sample_project.status == "active"

    # 验证可从 DB 读出
    fetched = project_repo.get_by_id("test-project")
    assert fetched is not None
    assert fetched.name == "测试项目"


def test_02_list_projects(project_repo, sample_project):
    """list_projects 正常。"""
    all_projects = project_repo.list_projects("all")
    assert len(all_projects) >= 1
    active = project_repo.list_active()
    assert all(p.status == "active" for p in active)


def test_03_update_project_status(project_repo, sample_project, audit_repo):
    """update_status 成功且写 audit_log。"""
    updated = project_repo.update_status(
        sample_project.id, "archived", actor="tester", reason="测试归档"
    )
    assert updated is not None
    assert updated.status == "archived"

    # 验证 audit_log 写入
    logs = audit_repo.list_by_project_id(sample_project.id, limit=10)
    status_logs = [l for l in logs if l["action"] == "project_status_changed"]
    assert len(status_logs) >= 1
    assert status_logs[0]["actor"] == "tester"


# ------------------------------------------------------------------
# 测试：MemoryItem CRUD
# ------------------------------------------------------------------

def test_04_create_memory(memory_repo, sample_project, sample_memory):
    """创建 memory_item 成功。"""
    assert sample_memory.id != ""
    assert sample_memory.project_id == sample_project.id
    assert sample_memory.status == "candidate"
    assert sample_memory.title == "订单查询接口事务注解"

    # 验证可从 DB 读出
    fetched = memory_repo.get_by_id(sample_memory.id)
    assert fetched is not None
    assert fetched.content == sample_memory.content


def test_05_find_by_hash(memory_repo, sample_project, sample_memory):
    """find_by_hash 能找到已存在的知识。"""
    found = memory_repo.find_by_hash(sample_memory.content_hash, sample_project.id)
    assert found is not None
    assert found.id == sample_memory.id

    # 不同项目的相同哈希也能区分
    not_found = memory_repo.find_by_hash(sample_memory.content_hash, "other-project")
    assert not_found is None


def test_06_list_memories(memory_repo, sample_project, sample_memory):
    """list_memories 支持过滤。"""
    # 全部
    all_mems = memory_repo.list_memories(sample_project.id)
    assert len(all_mems) >= 1

    # 按状态过滤
    candidates = memory_repo.list_memories(sample_project.id, status_filter=["candidate"])
    assert all(m.status == "candidate" for m in candidates)

    # 按类型过滤
    apis = memory_repo.list_memories(sample_project.id, type_filter="api")
    assert all(m.type == "api" for m in apis)

    # 按标签过滤
    tagged = memory_repo.list_memories(sample_project.id, tag_filter="spring")
    assert len(tagged) >= 1


def test_07_update_status_no_delete(memory_repo, sample_memory):
    """update_status 不物理删除 memory_item。"""
    # 先批准
    approved = memory_repo.update_status(
        sample_memory.id, "approved", actor="tester", reason="审核通过"
    )
    assert approved is not None
    assert approved.status == "approved"

    # 再废弃
    deprecated = memory_repo.update_status(
        sample_memory.id, "deprecated", actor="tester", reason="知识过期"
    )
    assert deprecated is not None
    assert deprecated.status == "deprecated"

    # 验证数据仍然存在（未物理删除）
    still_there = memory_repo.get_by_id(sample_memory.id)
    assert still_there is not None
    assert still_there.id == sample_memory.id


def test_08_update_memory_fields(memory_repo, sample_memory):
    """update_memory 可以更新字段但不能改 status。"""
    updated = memory_repo.update_memory(
        sample_memory.id,
        {"title": "新标题", "confidence": 0.95},
        actor="tester",
        reason="更新标题",
    )
    assert updated is not None
    assert updated.title == "新标题"
    assert updated.confidence == 0.95
    # status 不应该被 update_memory 修改
    assert updated.status == "candidate"


# ------------------------------------------------------------------
# 测试：Tags
# ------------------------------------------------------------------

def test_09_tags_association(memory_repo, sample_memory):
    """memory_tags 能关联 memory_item。"""
    tags = memory_repo.list_tags(sample_memory.id)
    assert len(tags) >= 3  # order, transaction, spring
    tag_names = [t["tag"] for t in tags]
    assert "order" in tag_names
    assert "transaction" in tag_names
    assert "spring" in tag_names

    # 添加新标签
    memory_repo.add_tag(sample_memory.id, "test-tag", category="general")
    tags_after = memory_repo.list_tags(sample_memory.id)
    assert any(t["tag"] == "test-tag" for t in tags_after)

    # 移除标签
    memory_repo.remove_tag(sample_memory.id, "test-tag")
    tags_final = memory_repo.list_tags(sample_memory.id)
    assert not any(t["tag"] == "test-tag" for t in tags_final)


# ------------------------------------------------------------------
# 测试：Relations
# ------------------------------------------------------------------

def test_10_relations_between_items(memory_repo, sample_project, sample_memory):
    """memory_relations 能关联两条 memory_item。"""
    # 创建第二条知识
    content2 = "订单查询接口现在使用缓存优化"
    item2 = MemoryItem(
        project_id=sample_project.id,
        module="订单管理",
        type="architecture",
        title="订单查询缓存优化",
        content=content2,
        content_hash=compute_content_hash(content2),
        status="candidate",
        source_type="ai_inferred",
    )
    mem2 = memory_repo.create_memory(item2, actor="test_runner")

    # 建立关联
    memory_repo.add_relation(
        sample_memory.id, mem2.id, "related_to", "都是订单查询相关"
    )

    relations_a = memory_repo.list_relations(sample_memory.id)
    assert len(relations_a) >= 1
    assert relations_a[0]["relation_type"] == "related_to"

    relations_b = memory_repo.list_relations(mem2.id)
    assert len(relations_b) >= 1


def test_11_remove_relation(memory_repo, sample_project, sample_memory):
    """移除关联正常。"""
    content2 = "关联测试知识"
    item2 = MemoryItem(
        project_id=sample_project.id,
        type="other",
        title="关联测试",
        content=content2,
        content_hash=compute_content_hash(content2),
    )
    mem2 = memory_repo.create_memory(item2, actor="test_runner")
    memory_repo.add_relation(sample_memory.id, mem2.id, "depends_on")

    relations_before = memory_repo.list_relations(sample_memory.id)
    assert len(relations_before) >= 1

    memory_repo.remove_relation(sample_memory.id, mem2.id, "depends_on")
    relations_after = memory_repo.list_relations(sample_memory.id)
    assert len(relations_after) == len(relations_before) - 1


# ------------------------------------------------------------------
# 测试：Audit Log
# ------------------------------------------------------------------

def test_12_audit_log_written(memory_repo, audit_repo, sample_memory):
    """audit_log 写入成功。"""
    logs = audit_repo.list_by_memory_id(sample_memory.id)
    assert len(logs) >= 1
    assert logs[0]["action"] == "memory_created"
    assert logs[0]["actor"] == "test_runner"


def test_13_status_change_audited(memory_repo, audit_repo, sample_memory):
    """状态变更写 audit_log。"""
    memory_repo.update_status(
        sample_memory.id, "approved", actor="reviewer", reason="确认正确"
    )
    logs = audit_repo.list_by_memory_id(sample_memory.id)
    status_logs = [l for l in logs if l["action"] == "status_changed"]
    assert len(status_logs) >= 1
    assert status_logs[0]["actor"] == "reviewer"
    assert "candidate → approved" in status_logs[0]["reason"]


# ------------------------------------------------------------------
# 测试：约束
# ------------------------------------------------------------------

def test_14_foreign_keys_enforced(memory_repo):
    """foreign_keys 生效 — 引用不存在的 project 会失败。"""
    bad_item = MemoryItem(
        project_id="non-existent-project",
        type="other",
        title="测试",
        content="test",
        content_hash=compute_content_hash("test"),
    )
    with pytest.raises(sqlite3.IntegrityError):
        memory_repo.create_memory(bad_item, actor="test_runner")


def test_15_wal_mode(conn):
    """WAL 模式开启。"""
    row = conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0].lower() == "wal"


def test_16_multiple_items_same_project(memory_repo, sample_project):
    """同一项目下可创建多条知识。"""
    for i in range(3):
        content = f"测试知识 #{i}"
        item = MemoryItem(
            project_id=sample_project.id,
            type="other",
            title=f"测试 #{i}",
            content=content,
            content_hash=compute_content_hash(content),
        )
        memory_repo.create_memory(item, actor="test_runner")

    all_mems = memory_repo.list_memories(sample_project.id)
    # 本测试未依赖 sample_memory fixture，所以至少有 3 条
    assert len(all_mems) >= 3


# ------------------------------------------------------------------
# Phase 2.5 新增：Project audit 持久化
# ------------------------------------------------------------------

def test_17_project_audit_persisted_after_reopen(db_path):
    """project 写入后关闭连接再打开，audit_log 仍然存在。"""
    # 创建
    db1 = DatabaseConnection(db_path)
    conn1 = db1.connect()
    repo1 = ProjectRepository(conn1)
    p = Project(id="persist-test", name="持久化测试", slug="persist-test",
                status="active", root_paths=["D:/test"], tech_stack=["python"])
    repo1.upsert_project(p, actor="test_runner", reason="持久化测试")
    db1.close()

    # 重新打开
    db2 = DatabaseConnection(db_path)
    conn2 = db2.connect()
    audit_repo2 = AuditRepository(conn2)
    project_repo2 = ProjectRepository(conn2)

    # 验证 project 存在
    reloaded = project_repo2.get_by_id("persist-test")
    assert reloaded is not None
    assert reloaded.name == "持久化测试"

    # 验证 audit_log 存在
    logs = audit_repo2.list_by_project_id("persist-test")
    assert len(logs) >= 1
    assert logs[0]["action"] == "project_created"
    db2.close()


def test_18_project_update_status_audit_persisted_after_reopen(db_path):
    """update_status 后关闭连接，再打开 audit_log 仍然存在。"""
    db1 = DatabaseConnection(db_path)
    conn1 = db1.connect()
    repo1 = ProjectRepository(conn1)
    p = Project(id="status-test", name="状态测试", slug="status-test",
                status="active", root_paths=["D:/test"], tech_stack=["python"])
    repo1.upsert_project(p, actor="test_runner")
    repo1.update_status("status-test", "archived", actor="admin", reason="归档")
    db1.close()

    # 重新打开
    db2 = DatabaseConnection(db_path)
    conn2 = db2.connect()
    project_repo2 = ProjectRepository(conn2)
    audit_repo2 = AuditRepository(conn2)

    reloaded = project_repo2.get_by_id("status-test")
    assert reloaded.status == "archived"

    logs = audit_repo2.list_by_project_id("status-test")
    status_logs = [l for l in logs if l["action"] == "project_status_changed"]
    assert len(status_logs) >= 1
    assert status_logs[0]["actor"] == "admin"
    db2.close()


# ------------------------------------------------------------------
# Phase 2.5 新增：Tags 返回验证
# ------------------------------------------------------------------

def test_19_tags_in_create_memory(memory_repo, sample_project):
    """create_memory(tags=[\"a\",\"b\"]) 后，返回对象 tags 包含 a,b。"""
    content = "标签测试知识"
    item = MemoryItem(
        project_id=sample_project.id,
        type="other",
        title="标签测试",
        content=content,
        content_hash=compute_content_hash(content),
        tags=["alpha", "beta"],
    )
    created = memory_repo.create_memory(item, actor="test_runner")
    assert "alpha" in created.tags
    assert "beta" in created.tags
    assert len(created.tags) >= 2


def test_20_tags_in_get_by_id(memory_repo, sample_project):
    """get_by_id 返回对象 tags 包含已保存标签。"""
    content = "get_by_id 标签测试"
    item = MemoryItem(
        project_id=sample_project.id,
        type="other",
        title="get_by_id 标签",
        content=content,
        content_hash=compute_content_hash(content),
        tags=["gamma"],
    )
    created = memory_repo.create_memory(item, actor="test_runner")
    fetched = memory_repo.get_by_id(created.id)
    assert "gamma" in fetched.tags


def test_21_tags_in_list_memories(memory_repo, sample_project):
    """list_memories 返回对象的 tags 包含已保存标签。"""
    content = "list_memories 标签测试"
    item = MemoryItem(
        project_id=sample_project.id,
        type="other",
        title="list 标签",
        content=content,
        content_hash=compute_content_hash(content),
        tags=["delta"],
    )
    memory_repo.create_memory(item, actor="test_runner")
    results = memory_repo.list_memories(sample_project.id, tag_filter="delta")
    assert len(results) >= 1
    assert "delta" in results[0].tags

# ------------------------------------------------------------------
# Phase 2.6 新增：时间格式测试
# ------------------------------------------------------------------

def test_22_tag_created_at_iso_utc(memory_repo, sample_memory):
    """memory_tags.created_at 包含 T 和 Z。"""
    memory_repo.add_tag(sample_memory.id, "time-test", category="general")
    memory_repo.conn.commit()
    tags = memory_repo.list_tags(sample_memory.id)
    time_tags = [t for t in tags if t["tag"] == "time-test"]
    assert len(time_tags) >= 1
    created_at = time_tags[0]["created_at"]
    assert "T" in created_at, f"缺少 T: {created_at}"
    assert created_at.endswith("Z"), f"缺少 Z: {created_at}"

def test_23_relation_created_at_iso_utc(memory_repo, sample_project, sample_memory):
    """memory_relations.created_at 包含 T 和 Z。"""
    content2 = "relation time test"
    item2 = MemoryItem(
        project_id=sample_project.id, type="other", title="关联时间测试",
        content=content2, content_hash=compute_content_hash(content2))
    mem2 = memory_repo.create_memory(item2, actor="test_runner")
    memory_repo.add_relation(sample_memory.id, mem2.id, "related_to", "时间测试")
    memory_repo.conn.commit()
    relations = memory_repo.list_relations(sample_memory.id)
    assert len(relations) >= 1
    created_at = relations[0]["created_at"]
    assert "T" in created_at, f"缺少 T: {created_at}"
    assert created_at.endswith("Z"), f"缺少 Z: {created_at}"

# ------------------------------------------------------------------
# Phase 2.7 新增：唯一约束测试
# ------------------------------------------------------------------

def test_24_duplicate_tag_only_one(memory_repo, sample_memory):
    """重复 add_tag 同一 memory_id/tag/category 只保留一条。"""
    memory_repo.add_tag(sample_memory.id, "unique-test", category="general")
    memory_repo.conn.commit()
    memory_repo.add_tag(sample_memory.id, "unique-test", category="general")
    memory_repo.conn.commit()
    tags = [t for t in memory_repo.list_tags(sample_memory.id) if t["tag"] == "unique-test"]
    assert len(tags) == 1

def test_25_duplicate_relation_only_one(memory_repo, sample_project, sample_memory):
    """重复 add_relation 同一 triple 只保留一条。"""
    content = "dup relation test"
    item2 = MemoryItem(project_id=sample_project.id, type="other", title="去重关联",
                       content=content, content_hash=compute_content_hash(content))
    mem2 = memory_repo.create_memory(item2, actor="test_runner")
    memory_repo.add_relation(sample_memory.id, mem2.id, "related_to", "去重测试")
    memory_repo.conn.commit()
    memory_repo.add_relation(sample_memory.id, mem2.id, "related_to", "去重测试2")
    memory_repo.conn.commit()
    relations = [r for r in memory_repo.list_relations(sample_memory.id)
                 if r["memory_id_b"] == mem2.id]
    assert len(relations) == 1

# ------------------------------------------------------------------
# Phase 2.7 新增：or 默认值修复测试
# ------------------------------------------------------------------

def test_26_project_auto_approve_zero(project_repo):
    """Project.auto_approve_threshold = 0，读回仍然是 0。"""
    p = Project(id="zero-threshold", name="零阈值", slug="zero-threshold",
                status="active", root_paths=["D:/zero"], tech_stack=["py"],
                auto_approve_threshold=0)
    created = project_repo.upsert_project(p, actor="test")
    assert created.auto_approve_threshold == 0
    fetched = project_repo.get_by_id("zero-threshold")
    assert fetched.auto_approve_threshold == 0

def test_27_memory_confidence_zero(memory_repo, sample_project):
    """MemoryItem.confidence = 0，读回仍然是 0。"""
    content = "零置信度测试"
    item = MemoryItem(project_id=sample_project.id, type="other", title="零置信度",
                      content=content, content_hash=compute_content_hash(content),
                      confidence=0.0)
    created = memory_repo.create_memory(item, actor="test")
    assert created.confidence == 0.0
    fetched = memory_repo.get_by_id(created.id)
    assert fetched.confidence == 0.0

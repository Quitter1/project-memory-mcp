"""数据库迁移测试 — 验证 schema 初始化正确性。"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from project_memory_mcp.db.connection import DatabaseConnection
from project_memory_mcp.db.migrations import get_current_version, LATEST_VERSION, run_migrations


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def temp_db_path():
    """创建临时数据库文件路径。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    Path(path).unlink(missing_ok=True)  # 让 connection.py 自己创建
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def fresh_db(temp_db_path) -> sqlite3.Connection:
    """创建全新数据库并执行迁移。"""
    db = DatabaseConnection(temp_db_path)
    conn = db.connect()
    yield conn
    db.close()


# ------------------------------------------------------------------
# 测试：初始化
# ------------------------------------------------------------------

def test_01_init_creates_database(temp_db_path):
    """初始化数据库成功 — 文件被创建。"""
    db = DatabaseConnection(temp_db_path)
    conn = db.connect()
    assert Path(temp_db_path).exists()
    db.close()


def test_02_repeat_migration_no_error(fresh_db):
    """重复执行 migration 不报错。"""
    # fresh_db 已经执行过一次 migration
    # 再执行一次应该无错误（所有 CREATE 用 IF NOT EXISTS）
    version_before = get_current_version(fresh_db)
    run_migrations(fresh_db)
    version_after = get_current_version(fresh_db)
    assert version_before == version_after


def test_03_schema_version_correct(fresh_db):
    """schema version 正确。"""
    version = get_current_version(fresh_db)
    assert version == LATEST_VERSION
    assert version >= 1


# ------------------------------------------------------------------
# 测试：表存在
# ------------------------------------------------------------------

def test_04_projects_table_exists(fresh_db):
    """projects 表存在。"""
    row = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
    ).fetchone()
    assert row is not None


def test_05_memory_items_table_exists(fresh_db):
    """memory_items 表存在。"""
    row = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_items'"
    ).fetchone()
    assert row is not None


def test_06_memory_tags_table_exists(fresh_db):
    """memory_tags 表存在。"""
    row = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_tags'"
    ).fetchone()
    assert row is not None


def test_07_memory_relations_table_exists(fresh_db):
    """memory_relations 表存在。"""
    row = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_relations'"
    ).fetchone()
    assert row is not None


def test_08_audit_log_table_exists(fresh_db):
    """audit_log 表存在。"""
    row = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
    ).fetchone()
    assert row is not None


# ------------------------------------------------------------------
# 测试：PRAGMA
# ------------------------------------------------------------------

def test_09_foreign_keys_enabled(fresh_db):
    """foreign_keys 生效。"""
    row = fresh_db.execute("PRAGMA foreign_keys").fetchone()
    assert row[0] == 1


def test_10_wal_mode_enabled(fresh_db):
    """WAL 模式开启。"""
    row = fresh_db.execute("PRAGMA journal_mode").fetchone()
    assert row[0].lower() == "wal"


# ------------------------------------------------------------------
# 测试：索引存在
# ------------------------------------------------------------------

def test_11_essential_indexes_exist(fresh_db):
    """关键索引存在。"""
    indexes = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
    ).fetchall()
    index_names = {r["name"] for r in indexes}
    required = [
        "idx_memory_project_id",
        "idx_memory_status",
        "idx_memory_content_hash",
        "idx_memory_project_status",
        "idx_audit_memory",
        "idx_projects_slug",
    ]
    for idx in required:
        assert idx in index_names, f"缺少索引: {idx}"

# ------------------------------------------------------------------
# Phase 2.7 新增：migration v2 测试
# ------------------------------------------------------------------

def test_12_schema_version_is_2(fresh_db):
    """PRAGMA user_version == 2。"""
    v = fresh_db.execute("PRAGMA user_version").fetchone()[0]
    assert v == 2

def test_13_migration_v2_repeat_no_error(fresh_db):
    """重复执行 migration v2 不报错。"""
    from project_memory_mcp.db.migrations import run_migrations
    run_migrations(fresh_db)  # 不应抛异常

def test_14_unique_indexes_exist(fresh_db):
    """唯一索引存在。"""
    indexes = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE '%unique%'"
    ).fetchall()
    names = {r["name"] for r in indexes}
    assert "idx_tags_unique" in names
    assert "idx_relations_unique" in names

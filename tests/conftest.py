"""测试 fixtures — 临时 SQLite 数据库、mock 组件。"""

import pytest
import sqlite3
import tempfile
from pathlib import Path


@pytest.fixture
def temp_db():
    """创建临时 SQLite 数据库。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    yield conn
    conn.close()
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def sample_projects():
    """示例项目数据。"""
    return [
        {
            "id": "biaopai-erp",
            "name": "标牌 ERP",
            "slug": "biaopai-erp",
            "status": "active",
            "root_paths": '["D:/workspace/biaopai-erp"]',
            "tech_stack": '["Java", "Spring MVC", "MySQL"]',
            "aliases": '["erp", "biaopai"]',
            "auto_approve_threshold": -1,
        },
        {
            "id": "cdr-converter",
            "name": "CDR 转图片工具",
            "slug": "cdr-converter",
            "status": "active",
            "root_paths": '["D:/workspace/cdr-converter"]',
            "tech_stack": '["Python", "Tkinter"]',
            "aliases": '["cdr转换", "coreldraw"]',
            "auto_approve_threshold": 0.9,
        },
        {
            "id": "old-tool",
            "name": "旧工具项目（已归档）",
            "slug": "old-tool",
            "status": "archived",
            "root_paths": "[]",
            "tech_stack": "[]",
            "aliases": '["old-tool"]',
            "auto_approve_threshold": -1,
        },
    ]

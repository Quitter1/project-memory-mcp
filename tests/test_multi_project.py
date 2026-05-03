"""
多项目集成测试 — resolve + 跨项目隔离 + shared 可见性。

不接 Qdrant，不接 LLM Reviewer。
"""

import tempfile
from pathlib import Path

import pytest

from project_memory_mcp.app_context import AppContext
from project_memory_mcp.tools.handlers import ToolHandler
from project_memory_mcp.models.memory_item import MemoryItem
from project_memory_mcp.utils.hashing import compute_content_hash


def _write_projects_yml(config_dir: Path):
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "projects.yml").write_text("""\
projects:
  erp:
    name: "ERP"
    slug: "erp"
    status: active
    recognition:
      root_paths: ["D:/workspace/erp", "/workspace/erp"]
      aliases: ["erp", "ERP系统"]
      tech_stack_keywords: ["java", "spring", "mysql"]
      module_keywords: ["订单管理", "物料管理"]
    knowledge_policy:
      auto_approve_threshold: 0.8
    review_policy:
      allow_ai_auto_approve: false
  cdr:
    name: "CDR"
    slug: "cdr"
    status: active
    recognition:
      root_paths: ["D:/workspace/cdr", "/workspace/cdr"]
      aliases: ["cdr", "CorelDRAW"]
      tech_stack_keywords: ["python", "com", "pillow"]
    knowledge_policy:
      auto_approve_threshold: 0.8
    review_policy:
      allow_ai_auto_approve: true
  rpa:
    name: "RPA"
    slug: "rpa"
    status: active
    recognition:
      root_paths: ["D:/workspace/rpa", "/workspace/rpa"]
      aliases: ["rpa", "自动化客户端"]
      tech_stack_keywords: ["electron", "vue3", "typescript"]
    review_policy:
      allow_ai_auto_approve: true
  archived-proj:
    name: "已归档项目"
    slug: "archived-proj"
    status: archived
    recognition:
      root_paths: ["/workspace/old"]
      aliases: ["old"]
defaults:
  knowledge_policy:
    auto_approve_threshold: -1
    max_candidate_per_task: 20
    retention_days: 365
  review_policy:
    allow_ai_auto_approve: false
    forbidden_auto_types: []
    risk_threshold_for_review: medium
    require_review_if_conflict: true
""", encoding="utf-8")


@pytest.fixture
def ctx():
    tmp = Path(tempfile.mkdtemp())
    config_dir = tmp / "config"
    db_path = tmp / "memory.db"
    _write_projects_yml(config_dir)
    c = AppContext(config_dir=config_dir, db_path=db_path)
    c.sync_projects()
    yield c
    c.db.close()
    import shutil
    shutil.rmtree(str(tmp), ignore_errors=True)


@pytest.fixture
def handler(ctx):
    return ToolHandler(ctx)


# ── resolve ────────────────────────────────────────────────

class TestResolve:
    def test_workspace_path_erp(self, handler):
        r = handler.resolve_project({"workspace_path": "/workspace/erp/src/Controller.java"})
        assert r["ok"] is True
        assert r["data"]["project"]["slug"] == "erp"
        assert r["data"]["match_method"] == "workspace_path"

    def test_task_description_cdr(self, handler):
        r = handler.resolve_project({"task_description": "修改 CorelDRAW 转换工具的弹窗处理"})
        assert r["ok"] is True
        assert r["data"]["project"]["slug"] == "cdr"

    def test_related_files_rpa(self, handler):
        r = handler.resolve_project({"related_files": ["D:/workspace/rpa/src/main.ts"]})
        assert r["ok"] is True
        assert r["data"]["project"]["slug"] == "rpa"

    def test_explicit_archived(self, handler):
        r = handler.resolve_project({"project_id": "archived-proj"})
        assert r["ok"] is True


# ── 跨项目隔离 ─────────────────────────────────────────────

class TestCrossProjectIsolation:
    def _seed(self, ctx):
        items = [
            ("erp", "ERP私有知识", "erp private knowledge", "approved", "project", []),
            ("cdr", "CDR私有知识", "cdr private knowledge", "approved", "project", []),
            ("erp", "全局知识", "global knowledge for all", "approved", "global", []),
            ("erp", "ERP+CDR共享", "shared erp cdr", "approved", "shared", ["erp", "cdr"]),
            ("erp", "仅ERP共享", "shared only erp", "approved", "shared", ["erp"]),
        ]
        for pid, title, content, status, scope, allowed in items:
            h = compute_content_hash(content)
            existing = ctx.memory_repo.find_by_hash(h, pid, scope=scope)
            if existing is None:
                ctx.memory_repo.create_memory(MemoryItem(
                    id="", project_id=pid, title=title, content=content,
                    content_hash=h, type="other", status=status, scope=scope,
                    allowed_projects=allowed, source_type="user_confirmed",
                    confidence=0.9, risk_level="low",
                ), actor="test")

    def test_erp_not_see_cdr_private(self, handler, ctx):
        self._seed(ctx)
        r = handler.search_project_context({"project_id": "erp", "query": "CDR私有", "max_results": 20})
        cp = r["data"]["context_pack"]
        all_titles = []
        for g in ("project_context", "shared_context", "global_context"):
            all_titles.extend(x["title"] for x in cp.get(g, []))
        assert not any("CDR私有知识" in t for t in all_titles)

    def test_cdr_not_see_erp_private(self, handler, ctx):
        self._seed(ctx)
        r = handler.search_project_context({"project_id": "cdr", "query": "ERP私有", "max_results": 20})
        cp = r["data"]["context_pack"]
        all_titles = []
        for g in ("project_context", "shared_context", "global_context"):
            all_titles.extend(x["title"] for x in cp.get(g, []))
        assert not any("ERP私有知识" in t for t in all_titles)

    def test_all_see_global(self, handler, ctx):
        self._seed(ctx)
        for pid in ("erp", "cdr", "rpa"):
            r = handler.search_project_context({"project_id": pid, "query": "全局知识", "max_results": 20})
            gl = [x["title"] for x in r["data"]["context_pack"].get("global_context", [])]
            assert any("全局知识" in t for t in gl), f"{pid} 应看到 global"

    def test_erp_sees_allowed_shared(self, handler, ctx):
        self._seed(ctx)
        r = handler.search_project_context({"project_id": "erp", "query": "ERP+CDR共享", "max_results": 20})
        sh = [x["title"] for x in r["data"]["context_pack"].get("shared_context", [])]
        assert any("ERP+CDR共享" in t for t in sh)

    def test_cdr_sees_allowed_shared(self, handler, ctx):
        self._seed(ctx)
        r = handler.search_project_context({"project_id": "cdr", "query": "ERP+CDR共享", "max_results": 20})
        sh = [x["title"] for x in r["data"]["context_pack"].get("shared_context", [])]
        assert any("ERP+CDR共享" in t for t in sh)

    def test_cdr_not_see_erp_only_shared(self, handler, ctx):
        self._seed(ctx)
        r = handler.search_project_context({"project_id": "cdr", "query": "仅ERP共享", "max_results": 20})
        sh = [x["title"] for x in r["data"]["context_pack"].get("shared_context", [])]
        assert not any("仅ERP共享" in t for t in sh)

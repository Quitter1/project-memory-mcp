"""
端到端集成测试 — 多项目隔离 + propose/review/search 闭环 + 安全闭环 + MCP 格式。

使用真实 SQLite（临时文件），不接 Qdrant/LLM。
"""

import tempfile
from pathlib import Path

import pytest

from project_memory_mcp.app_context import AppContext
from project_memory_mcp.tools.handlers import ToolHandler


def _write_projects_yml(config_dir: Path):
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "projects.yml").write_text("""\
projects:
  erp:
    name: "ERP"
    slug: "erp"
    status: active
    recognition:
      root_paths: ["/workspace/erp"]
      aliases: ["erp", "ERP系统"]
      tech_stack_keywords: ["java", "spring"]
    knowledge_policy:
      auto_approve_threshold: 0.8
    review_policy:
      allow_ai_auto_approve: false
  cdr:
    name: "CDR"
    slug: "cdr"
    status: active
    recognition:
      root_paths: ["/workspace/cdr"]
      aliases: ["cdr", "CorelDRAW"]
      tech_stack_keywords: ["python", "com"]
    knowledge_policy:
      auto_approve_threshold: 0.8
    review_policy:
      allow_ai_auto_approve: true
  rpa:
    name: "RPA"
    slug: "rpa"
    status: active
    recognition:
      root_paths: ["/workspace/rpa"]
      aliases: ["rpa"]
      tech_stack_keywords: ["electron", "vue"]
    review_policy:
      allow_ai_auto_approve: true
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


# ── 多项目隔离 ──────────────────────────────────────────────

class TestMultiProjectIsolation:
    """多项目检索隔离。"""

    def _seed(self, ctx):
        """插入测试种子数据。"""
        from project_memory_mcp.models.memory_item import MemoryItem
        from project_memory_mcp.utils.hashing import compute_content_hash

        items = [
            ("erp", "ERP产品材料知识", "产品对应材料，优先关联 bj_comm_materials", "approved", "project", []),
            ("cdr", "CDR弹窗COM处理", "CorelDRAW COM 弹窗自动处理", "approved", "project", []),
            ("erp", "MySQL collation 1267", "遇到 1267 错误检查 collation", "approved", "global", []),
            ("erp", "共享审阅包流程", "阶段结束生成 review-pack", "approved", "shared", ["erp", "cdr"]),
        ]
        for pid, title, content, status, scope, allowed in items:
            ctx.memory_repo.create_memory(MemoryItem(
                id="", project_id=pid, title=title, content=content,
                content_hash=compute_content_hash(content), type="other",
                status=status, scope=scope, allowed_projects=allowed,
                source_type="user_confirmed", confidence=0.9, risk_level="low",
            ), actor="test")

    def test_01_erp_not_see_cdr_private(self, handler, ctx):
        """ERP 搜索不应返回 CDR 私有知识。"""
        self._seed(ctx)
        r = handler.search_project_context({"project_id": "erp", "query": "CorelDRAW COM"})
        items = []
        cp = r["data"]["context_pack"]
        for g in ("project_context", "shared_context", "global_context"):
            for item in cp.get(g, []):
                items.append(item.get("title", ""))
        assert not any("CDR弹窗" in t for t in items)

    def test_02_cdr_not_see_erp_private(self, handler, ctx):
        """CDR 搜索不应返回 ERP 私有知识。"""
        self._seed(ctx)
        r = handler.search_project_context({"project_id": "cdr", "query": "产品 材料"})
        items = []
        cp = r["data"]["context_pack"]
        for g in ("project_context", "shared_context", "global_context"):
            for item in cp.get(g, []):
                items.append(item.get("title", ""))
        assert not any("ERP产品材料" in t for t in items)

    def test_03_erp_can_see_global(self, handler, ctx):
        """ERP 可以搜索到 global scope 的知识。"""
        self._seed(ctx)
        r = handler.search_project_context({"project_id": "erp", "query": "collation 1267"})
        cp = r["data"]["context_pack"]
        titles = [x["title"] for x in cp.get("global_context", [])]
        assert any("MySQL collation 1267" in t for t in titles)

    def test_04_cdr_can_see_global(self, handler, ctx):
        """CDR 也可以搜索到 global scope 的知识。"""
        self._seed(ctx)
        r = handler.search_project_context({"project_id": "cdr", "query": "collation 1267"})
        cp = r["data"]["context_pack"]
        titles = [x["title"] for x in cp.get("global_context", [])]
        assert any("MySQL collation 1267" in t for t in titles)

    def test_05_erp_can_see_shared(self, handler, ctx):
        """shared allowed 包含 ERP，ERP 可搜索到 shared。"""
        self._seed(ctx)
        r = handler.search_project_context({"project_id": "erp", "query": "review-pack"})
        cp = r["data"]["context_pack"]
        titles = [x["title"] for x in cp.get("shared_context", [])]
        assert any("审阅包" in t for t in titles)


# ── propose/review/search 闭环 ──────────────────────────────

class TestReviewLoop:
    """propose → review → search 完整闭环。"""

    def test_01_propose_pending_review(self, handler):
        r = handler.propose_memory({
            "project_id": "erp", "title": "AI推测知识",
            "content": "由 AI 从代码推断的知识", "confidence": 0.5,
            "source_type": "ai_inferred", "actor": "test",
        })
        assert r["ok"] is True
        assert r["data"]["status"] == "pending_review"

    def test_02_list_shows_pending(self, handler):
        handler.propose_memory({
            "project_id": "erp", "title": "待审核知识",
            "content": "等待人工审核", "confidence": 0.5, "actor": "test",
        })
        r = handler.list_memories({"project_id": "erp", "status_filter": "pending_review"})
        titles = [m["title"] for m in r["data"]["memories"]]
        assert any("待审核知识" in t for t in titles)

    def test_03_approve_then_search(self, handler):
        pr = handler.propose_memory({
            "project_id": "erp", "title": "订单事务规范",
            "content": "订单查询必须加 @Transactional", "confidence": 0.5,
            "source_type": "ai_inferred", "actor": "test",
        })
        mid = pr["data"]["memory_id"]
        handler.approve_memory({"memory_id": mid, "reviewer": "admin"})

        r = handler.search_project_context({
            "project_id": "erp", "query": "事务",
            "max_results": 20,
        })
        cp = r["data"]["context_pack"]
        titles = [x["title"] for x in cp.get("project_context", [])]
        assert any("订单事务规范" in t for t in titles)

    def test_04_reject_not_in_search(self, handler):
        pr = handler.propose_memory({
            "project_id": "erp", "title": "错误知识ZZZ",
            "content": "不正确的推断", "confidence": 0.5, "actor": "test",
        })
        mid = pr["data"]["memory_id"]
        handler.reject_memory({"memory_id": mid, "reason": "不准确"})

        r = handler.search_project_context({"project_id": "erp", "query": "错误知识ZZZ", "max_results": 20})
        cp = r["data"]["context_pack"]
        titles = [x["title"] for x in cp.get("project_context", [])]
        assert not any("错误知识ZZZ" in t for t in titles)

    def test_05_deprecate_not_in_search(self, handler):
        pr = handler.propose_memory({
            "project_id": "erp", "title": "旧规范YYY",
            "content": "已过时的规范", "confidence": 0.9, "source_type": "user_confirmed",
            "actor": "test",
        })
        mid = pr["data"]["memory_id"]
        handler.approve_memory({"memory_id": mid})
        handler.deprecate_memory({"memory_id": mid, "reason": "过时"})

        r = handler.search_project_context({"project_id": "erp", "query": "旧规范YYY", "max_results": 20})
        cp = r["data"]["context_pack"]
        titles = [x["title"] for x in cp.get("project_context", [])]
        assert not any("旧规范YYY" in t for t in titles)


# ── 安全闭环 ──────────────────────────────────────────────

class TestSecurityLoop:
    """敏感信息检测 + audit_log 安全。"""

    def test_01_api_key_blocked(self, handler, ctx):
        r = handler.propose_memory({
            "project_id": "erp", "title": "泄露",
            "content": "-----BEGIN RSA PRIVATE KEY-----\ntest", "actor": "test",
        })
        assert r["ok"] is True
        assert r["data"]["status"] == "rejected"
        assert r["data"]["memory_id"] == ""

    def test_02_no_content_saved(self, handler, ctx):
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        handler.propose_memory({
            "project_id": "erp", "title": "私钥", "content": content, "actor": "test",
        })
        # 所有 knowledge 都不是这个 content
        all_items = ctx.memory_repo.list_memories("erp", limit=200)
        assert not any("MIIEpA" in (m.content or "") for m in all_items)

    def test_03_audit_log_no_raw_key(self, handler, ctx):
        handler.propose_memory({
            "project_id": "erp", "title": "标题",
            "content": "-----BEGIN RSA PRIVATE KEY-----\nblocked", "actor": "test",
        })
        logs = ctx.audit_repo.list_by_project_id("erp")
        blocked_logs = [l for l in logs if l.get("action") == "blocked"]
        assert len(blocked_logs) >= 1
        import json as _json
        nv = _json.dumps(blocked_logs[0].get("new_value") or {}, ensure_ascii=False)
        assert "RSA PRIVATE KEY" not in nv

    def test_04_source_evidence_key_blocked_audit_safe(self, handler, ctx):
        handler.propose_memory({
            "project_id": "erp", "title": "安全标题", "content": "安全内容",
            "source_evidence": {"OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456": "safe"},
            "actor": "test",
        })
        logs = ctx.audit_repo.list_by_project_id("erp")
        blocked_logs = [l for l in logs if l.get("action") == "blocked"]
        assert len(blocked_logs) >= 1
        import json as _json
        nv = _json.dumps(blocked_logs[0].get("new_value") or {}, ensure_ascii=False)
        assert "sk-proj" not in nv

    def test_05_tags_with_token_blocked(self, handler):
        r = handler.propose_memory({
            "project_id": "erp", "title": "安全标题", "content": "安全内容",
            "tags": ["ok", "token=ghp_abcdefghijklmnopqrstuvwxyz"],
            "actor": "test",
        })
        assert r["ok"] is True
        assert r["data"]["status"] == "rejected"


# ── MCP 格式 ──────────────────────────────────────────────

class TestMCPFormat:
    """所有 tool 返回格式验证。"""

    def test_01_all_success_have_ok_and_data(self, handler):
        tools_ok = [
            handler.list_projects({}),
            handler.resolve_project({"project_id": "erp"}),
            handler.get_project_profile({"project_id": "erp"}),
            handler.search_project_context({"project_id": "erp", "query": "test"}),
            handler.list_memories({"project_id": "erp"}),
        ]
        for r in tools_ok:
            assert r["ok"] is True
            assert "data" in r

    def test_02_all_errors_have_code(self, handler):
        errs = [
            handler.search_project_context({}),
            handler.list_memories({"project_id": ""}),
            handler.approve_memory({"memory_id": "nonexistent"}),
        ]
        for r in errs:
            assert r["ok"] is False
            assert "code" in r["error"]

    def test_03_search_has_full_fields(self, handler):
        r = handler.search_project_context({"project_id": "erp", "query": "test"})
        d = r["data"]
        for key in ("total_found", "total_returned", "search_method", "fallback_activated"):
            assert key in d, f"缺少 {key}"

    def test_04_context_pack_has_three_groups(self, handler):
        r = handler.search_project_context({"project_id": "erp", "query": "test"})
        cp = r["data"]["context_pack"]
        for key in ("project_context", "shared_context", "global_context"):
            assert key in cp, f"缺少 {key}"

    def test_05_error_no_traceback(self, handler):
        r = handler.approve_memory({"memory_id": "nonexistent"})
        text = str(r)
        assert "Traceback" not in text

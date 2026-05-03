"""
开发测试客户端 — 直接调用 ToolHandler，模拟 MCP client 行为。

用于人工调试 9 个 MCP tools 的功能正确性。

使用：
    python sandbox/test_mcp_client.py
"""

import json
import sys
import tempfile
from pathlib import Path

_src = Path(__file__).parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from project_memory_mcp.app_context import AppContext
from project_memory_mcp.tools.handlers import ToolHandler


def _setup() -> ToolHandler:
    """创建测试 context 和 handler。"""
    tmp = Path(tempfile.mkdtemp())
    config_dir = tmp / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "projects.yml").write_text("""\
projects:
  demo-proj:
    name: "演示项目"
    slug: "demo-proj"
    status: active
    recognition:
      root_paths:
        - "/demo"
      aliases:
        - "demo"
      tech_stack_keywords:
        - "python"
    knowledge_policy:
      auto_approve_threshold: 0.8
    review_policy:
      allow_ai_auto_approve: false
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

    db_path = tmp / "memory.db"
    ctx = AppContext(config_dir=config_dir, db_path=db_path)
    ctx.sync_projects()
    return ToolHandler(ctx)


def _print(title: str, result: dict):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    handler = _setup()

    # 1. list_projects
    _print("1. list_projects (active)", handler.list_projects({"status_filter": "active"}))

    # 2. resolve_project
    _print("2. resolve_project (id)", handler.resolve_project({"project_id": "demo-proj"}))

    # 3. get_project_profile
    _print("3. get_project_profile", handler.get_project_profile({"project_id": "demo-proj"}))

    # 4. search_project_context
    _print("4. search_project_context", handler.search_project_context({
        "project_id": "demo-proj",
        "query": "订单",
    }))

    # 5. propose_memory
    r = handler.propose_memory({
        "project_id": "demo-proj",
        "title": "演示知识",
        "content": "这是通过 sandbox 客户端提交的测试知识",
        "type": "architecture",
        "confidence": 0.5,
        "source_type": "ai_inferred",
        "actor": "sandbox",
    })
    _print("5. propose_memory", r)
    memory_id = r["data"].get("memory_id", "")

    # 6. list_memories
    _print("6. list_memories", handler.list_memories({"project_id": "demo-proj"}))

    # 7. approve_memory
    if memory_id:
        _print("7. approve_memory", handler.approve_memory({
            "memory_id": memory_id,
            "reviewer": "sandbox",
            "comment": "测试批准",
        }))

    # 8. propose + reject another
    r2 = handler.propose_memory({
        "project_id": "demo-proj",
        "title": "待拒绝的知识",
        "content": "这条会被拒绝",
        "confidence": 0.5,
        "actor": "sandbox",
    })
    mid2 = r2["data"].get("memory_id", "")
    if mid2:
        _print("8. reject_memory", handler.reject_memory({
            "memory_id": mid2,
            "reviewer": "sandbox",
            "reason": "测试拒绝",
        }))

    # 9. deprecate_memory
    if memory_id:
        _print("9. deprecate_memory", handler.deprecate_memory({
            "memory_id": memory_id,
            "reason": "已重构",
        }))

    # 10. propose_memory with blocked content
    _print("10. propose_memory (blocked)", handler.propose_memory({
        "project_id": "demo-proj",
        "title": "私钥泄露",
        "content": "-----BEGIN RSA PRIVATE KEY-----\ntest",
        "actor": "sandbox",
    }))

    print(f"\n{'='*60}")
    print("  所有 tool 测试完成")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

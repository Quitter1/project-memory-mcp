"""
端到端演示流程 — 本地人工验证完整闭环。

使用：
    python scripts/run_demo_flow.py
"""

import json
import sys
from pathlib import Path

_src = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(_src))

from project_memory_mcp.app_context import AppContext
from project_memory_mcp.tools.handlers import ToolHandler
from scripts.seed_demo_data import seed


def _print(title: str, result: dict):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    config_dir = Path(__file__).parent.parent / "config"
    db_path = Path(__file__).parent.parent / "data" / "memory.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    ctx = AppContext(config_dir=config_dir, db_path=db_path)
    ctx.sync_projects()
    handler = ToolHandler(ctx)

    # 1. 填充演示数据（幂等）
    seed_result = seed(ctx)
    print(f"演示数据: 新增 {seed_result['created']}, 跳过 {seed_result['skipped']}")

    # 2. list_projects
    _print("2. list_projects", handler.list_projects({}))

    # 3. search ERP 项目
    _print("3. search ERP: 产品 材料", handler.search_project_context({
        "project_id": "biaopai-erp", "query": "产品 材料",
    }))

    # 4. search CDR 项目
    _print("4. search CDR: CorelDRAW 弹窗", handler.search_project_context({
        "project_id": "cdr-converter", "query": "CorelDRAW 弹窗",
    }))

    # 5. search global (MySQL collation)
    _print("5. search ERP: collation 1267 (global)", handler.search_project_context({
        "project_id": "biaopai-erp", "query": "collation 1267",
    }))

    # 6. propose 普通知识
    pr = handler.propose_memory({
        "project_id": "biaopai-erp",
        "title": "ERP 订单模块需要加事务注解",
        "content": "OrderController 的 query 方法缺少 @Transactional，高并发下可能导致数据不一致。",
        "type": "code_pattern",
        "module": "订单管理",
        "confidence": 0.5,
        "source_type": "ai_inferred",
        "actor": "demo-flow",
    })
    _print("6. propose_memory(普通)", pr)
    mid = pr["data"].get("memory_id", "")

    # 7. list pending_review
    _print("7. list_memories(pending_review)", handler.list_memories({
        "project_id": "biaopai-erp", "status_filter": "pending_review",
    }))

    # 8. approve
    if mid:
        _print("8. approve_memory", handler.approve_memory({
            "memory_id": mid, "reviewer": "demo", "comment": "确认正确",
        }))

    # 9. re-search — should find approved
    _print("9. re-search: 订单 事务", handler.search_project_context({
        "project_id": "biaopai-erp", "query": "订单 事务",
    }))

    # 10. propose blocked
    br = handler.propose_memory({
        "project_id": "biaopai-erp",
        "title": "私钥泄露测试",
        "content": "-----BEGIN RSA PRIVATE KEY-----\ntest",
        "actor": "demo-flow",
    })
    _print("10. propose_memory(blocked)", br)

    # 11. resolve
    _print("11. resolve_project(workspace)", handler.resolve_project({
        "workspace_path": "D:/workspace/biaopai-erp",
    }))

    ctx.db.close()
    print(f"\n{'=' * 50}")
    print("  演示流程完成")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()

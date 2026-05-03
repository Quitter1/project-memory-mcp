"""
端到端演示流程 — 本地人工验证完整闭环。

使用：
    python scripts/run_demo_flow.py

环境变量：
    PROJECT_MEMORY_CONFIG_DIR / PROJECT_MEMORY_DB_PATH

exit 0 = 全部关键步骤通过, exit 1 = 有失败
"""

import json
import sys

import _paths
_ = _paths.ensure_import_paths()

from project_memory_mcp.app_context import AppContext
from project_memory_mcp.tools.handlers import ToolHandler
from scripts.seed_demo_data import seed


def _print(title: str, result: dict):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _check(title: str, result: dict, failures: list, ok_required=True):
    _print(title, result)
    if ok_required and not result.get("ok"):
        failures.append(f"{title}: ok=false, error={result.get('error', {}).get('code', 'unknown')}")


def main():
    config_dir, db_path = _paths.get_project_paths()
    ctx = AppContext(config_dir=config_dir, db_path=db_path)
    ctx.sync_projects()
    handler = ToolHandler(ctx)
    failures: list[str] = []

    # 1. 填充演示数据
    seed_result = seed(ctx)
    print(f"演示数据: 新增 {seed_result['created']}, 跳过 {seed_result['skipped']},"
          f" 缺失项目 {seed_result.get('missing_project', 0)}")

    # 2. list_projects
    _check("2. list_projects", handler.list_projects({}), failures)

    # 3. search ERP
    _check("3. search ERP: 产品 材料", handler.search_project_context({
        "project_id": "biaopai-erp", "query": "产品 材料",
    }), failures)

    # 4. search CDR
    _check("4. search CDR: CorelDRAW 弹窗", handler.search_project_context({
        "project_id": "cdr-converter", "query": "CorelDRAW 弹窗",
    }), failures)

    # 5. search global
    _check("5. search: collation 1267 (global)", handler.search_project_context({
        "project_id": "biaopai-erp", "query": "collation 1267",
    }), failures)

    # 6. propose
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
    _check("6. propose_memory(普通)", pr, failures)
    mid = ""
    if pr.get("ok") and pr.get("data"):
        mid = pr["data"].get("memory_id", "")

    # 7. list pending
    _check("7. list_memories(pending_review)", handler.list_memories({
        "project_id": "biaopai-erp", "status_filter": "pending_review",
    }), failures)

    # 8. approve
    if mid:
        _check("8. approve_memory", handler.approve_memory({
            "memory_id": mid, "reviewer": "demo", "comment": "确认正确",
        }), failures)

    # 9. re-search
    _check("9. re-search: 订单 事务", handler.search_project_context({
        "project_id": "biaopai-erp", "query": "订单 事务",
    }), failures)

    # 10. propose blocked
    br = handler.propose_memory({
        "project_id": "biaopai-erp",
        "title": "私钥泄露测试",
        "content": "-----BEGIN RSA PRIVATE KEY-----\ntest",
        "actor": "demo-flow",
    })
    # blocked 返回 ok=true + status=rejected，不算失败
    _print("10. propose_memory(blocked)", br)
    if br.get("ok") and br.get("data", {}).get("status") != "rejected":
        failures.append("10. propose_memory(blocked): 预期 rejected, 实际未 blocked")

    # 11. resolve
    _check("11. resolve_project(workspace)", handler.resolve_project({
        "workspace_path": "D:/workspace/biaopai-erp",
    }), failures)

    ctx.db.close()

    print(f"\n{'=' * 50}")
    if failures:
        print(f"  演示流程失败 ({len(failures)} 项)")
        for f in failures:
            print(f"    - {f}")
        print(f"{'=' * 50}")
        sys.exit(1)
    else:
        print("  演示流程完成")
        print(f"{'=' * 50}")


if __name__ == "__main__":
    main()

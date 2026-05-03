"""
演示数据填充脚本 — 幂等可重复运行。

使用：
    python scripts/seed_demo_data.py

环境变量：
    PROJECT_MEMORY_CONFIG_DIR — 配置目录
    PROJECT_MEMORY_DB_PATH — 数据库路径
"""

import sys

import _paths
_ = _paths.ensure_import_paths()

from project_memory_mcp.app_context import AppContext
from project_memory_mcp.models.memory_item import MemoryItem
from project_memory_mcp.utils.hashing import compute_content_hash

DEMO_DATA = [
    # ── biaopai-erp ──────────────────────────────────
    {
        "project_id": "biaopai-erp",
        "title": "ERP 报表中产品通常对应材料",
        "content": "在该 ERP 项目的报表语境中，页面上的\"产品\"通常对应系统中的\"材料\"，优先关联 bj_comm_materials。",
        "type": "business_rule",
        "status": "approved",
        "scope": "project",
        "tags": ["erp", "材料", "bj_comm_materials"],
        "source_type": "user_confirmed",
    },
    {
        "project_id": "biaopai-erp",
        "title": "pm_sc_task 可能用于工厂生产任务统计",
        "content": "pm_sc_task 保存生产任务数据，provider_id/provider_name 可用于供应商或工厂过滤，具体字段使用前应结合当前表结构验证。",
        "type": "data_structure",
        "status": "pending_review",
        "scope": "project",
        "tags": ["pm_sc_task", "工厂", "生产任务"],
        "source_type": "ai_inferred",
    },
    {
        "project_id": "biaopai-erp",
        "title": "旧 hd 框架不要随意 new Service",
        "content": "旧 hd 框架中 Service 获取方式需要参考现有 Controller 写法，不要随意 new Service。",
        "type": "code_pattern",
        "status": "approved",
        "scope": "project",
        "tags": ["hd框架", "Service", "Controller"],
        "source_type": "code_verified",
    },
    # ── cdr-converter ────────────────────────────────
    {
        "project_id": "cdr-converter",
        "title": "CorelDRAW 弹窗处理必须记录日志",
        "content": "CDR 转图片工具中，CorelDRAW 弹窗自动处理必须记录日志，并在异常路径中关闭和重启 CorelDRAW COM。",
        "type": "code_pattern",
        "status": "approved",
        "scope": "project",
        "tags": ["CorelDRAW", "COM", "弹窗"],
        "source_type": "code_verified",
    },
    # ── rpa-electron ──────────────────────────────────
    {
        "project_id": "rpa-electron",
        "title": "Electron RPA 页面嵌入使用 webview",
        "content": "Electron RPA 客户端通过 webview 嵌入目标页面，右侧显示运行日志和调试面板。",
        "type": "architecture",
        "status": "approved",
        "scope": "project",
        "tags": ["Electron", "webview", "RPA"],
        "source_type": "user_confirmed",
    },
    # ── global ───────────────────────────────────────
    {
        "project_id": "img-vector-search",
        "title": "MySQL 1267 collation 错误排查",
        "content": "遇到 1267 Illegal mix of collations 时，优先检查 JOIN 或 WHERE 条件两侧字段 collation 是否一致。",
        "type": "troubleshooting",
        "status": "approved",
        "scope": "global",
        "tags": ["MySQL", "1267", "collation"],
        "source_type": "user_confirmed",
    },
    # ── shared ───────────────────────────────────────
    {
        "project_id": "biaopai-erp",
        "title": "Claude Code 阶段结束必须生成审阅包",
        "content": "每个阶段完成后必须运行测试并生成 review-pack，用于外部审阅。",
        "type": "process",
        "status": "approved",
        "scope": "shared",
        "tags": ["Claude Code", "review-pack"],
        "source_type": "user_confirmed",
        "allowed_projects": ["biaopai-erp", "cdr-converter", "rpa-electron", "img-vector-search"],
    },
]


def _existing_key_set(ctx):
    """返回已存在的 (project_id, scope, content_hash) 集合。"""
    keys = set()
    for d in DEMO_DATA:
        h = compute_content_hash(d["content"])
        existing = ctx.memory_repo.find_by_hash(
            h, d["project_id"], scope=d["scope"],
            active_statuses={"approved", "pending_review", "candidate", "conflict"},
        )
        if existing is not None:
            keys.add((d["project_id"], d["scope"], h))
    return keys


def seed(ctx: AppContext) -> dict:
    ctx.sync_projects()
    existing_keys = _existing_key_set(ctx)
    created = 0
    skipped = 0
    missing_proj = 0

    for d in DEMO_DATA:
        # 跳过不存在的项目
        if ctx.config_loader.get_project(d["project_id"]) is None:
            missing_proj += 1
            continue

        h = compute_content_hash(d["content"])
        k = (d["project_id"], d["scope"], h)
        if k in existing_keys:
            skipped += 1
            continue

        item = MemoryItem(
            id="",
            project_id=d["project_id"],
            type=d["type"],
            title=d["title"],
            content=d["content"],
            content_hash=h,
            status=d["status"],
            index_status="not_indexed",
            scope=d["scope"],
            source_type=d.get("source_type", "user_confirmed"),
            tags=d.get("tags", []),
            allowed_projects=d.get("allowed_projects", []),
            confidence=0.9,
            risk_level="low",
        )
        ctx.memory_repo.create_memory(item, actor="seed_demo_data", reason="演示数据填充")
        created += 1
        existing_keys.add(k)

    return {"created": created, "skipped": skipped, "missing_project": missing_proj, "total": len(DEMO_DATA)}


def main():
    allow_missing = "--allow-missing-projects" in sys.argv
    config_dir, db_path = _paths.get_project_paths()
    ctx = AppContext(config_dir=config_dir, db_path=db_path)
    result = seed(ctx)
    print(f"演示数据填充完成: 新增 {result['created']}, 跳过 {result['skipped']},"
          f" 缺失项目 {result['missing_project']}, 总计 {result['total']}")
    ctx.db.close()

    # 全部缺失且未允许 → exit 1
    if result["missing_project"] > 0 and result["created"] + result["skipped"] == 0:
        if allow_missing:
            print("警告: 部分 demo 项目不在配置中，已允许跳过")
        else:
            print("错误: 所有 demo 数据项目均不在当前配置中。")
            print("  请确认 config/projects.yml 包含 biaopai-erp/cdr-converter/rpa-electron/img-vector-search")
            print("  或使用 --allow-missing-projects 跳过")
            sys.exit(1)


if __name__ == "__main__":
    main()

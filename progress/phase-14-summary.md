# 阶段 14 — 部署方案 / Agent 使用规范

## 完成时间

2026-05-04

## 新增文档

| 文件 | 说明 |
|------|------|
| `docs/deployment.md` | 部署指南（模式/目录/端口/启动顺序/安全） |
| `docs/agent-usage-guide.md` | Agent 使用规范（查/不自动沉淀/内容要求/审核） |
| `docs/agent-skill-template.md` | Agent Skill 模板（可复制到其他项目 CLAUDE.md） |
| `docs/production-checklist.md` | 正式使用检查清单（启动前/每周/升级/API Key） |

## 新增脚本

| 脚本 | 说明 |
|------|------|
| `scripts/ops/health_check.ps1` | 健康检查（embedding/qdrant/diagnose/eval） |
| `scripts/ops/backup_memory_db.ps1` | 备份 memory.db/config（不含 logs/reviews/API Key） |
| `scripts/ops/stop_project_memory.ps1` | 停止 / 列出 MCP 相关进程 |
| `scripts/ops/e2e_usage_check.ps1` | 端到端使用验收 |
| `scripts/ops/start_all_dev.ps1` | 开发用启动辅助 |

## 测试结果

```
420 passed in 13.28s
```

| 测试文件 | 新增 | 说明 |
|----------|------|------|
| test_deployment_docs.py | 13 (新) | 文档存在性 + 关键内容检查 |

**新增测试总计：+13**（原 407 → 420）

## 修改文件

| 文件 | 变更 |
|------|------|
| `docs/deployment.md` | 新增 |
| `docs/agent-usage-guide.md` | 新增 |
| `docs/agent-skill-template.md` | 新增 |
| `docs/production-checklist.md` | 新增 |
| `scripts/ops/health_check.ps1` | 新增 |
| `scripts/ops/backup_memory_db.ps1` | 新增 |
| `scripts/ops/stop_project_memory.ps1` | 新增 |
| `scripts/ops/e2e_usage_check.ps1` | 新增 |
| `scripts/ops/start_all_dev.ps1` | 新增 |
| `tests/test_deployment_docs.py` | 新增 |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-14.zip`

## 是否可以进入真实使用试运行

✅ 可以。按 `docs/deployment.md` 部署，按 `docs/agent-usage-guide.md` 规范使用。

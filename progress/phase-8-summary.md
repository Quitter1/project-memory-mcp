# 阶段 8 报告 — 真实使用回路打磨

## 完成时间

2026-05-03

## 新增文档

| 文件 | 说明 |
|------|------|
| `docs/claude-code-memory-workflow.md` | Claude Code 使用规范（禁止自动 propose） |
| `docs/memory-review-guide.md` | 审核标准（可 approve/应 reject/应 deprecate） |
| `docs/prompts/task-start-search.md` | 任务开始搜索提示词 |
| `docs/prompts/task-end-memory-proposal.md` | 任务结束知识沉淀提示词 |
| `docs/prompts/review-pending-memory.md` | 审核待处理知识提示词 |

## 新增脚本

| 文件 | 说明 |
|------|------|
| `scripts/review_memories.py` | list/show/approve/reject/deprecate，默认 dry-run |
| `scripts/cleanup_test_memories.py` | 清理 [CC_TEST]/[STDIO_TEST] 测试知识 |

## 增强

| 文件 | 变更 |
|------|------|
| `scripts/diagnose.py` | --review-summary（待审核/测试/blocked/duplicate_rejected 统计） |
| `README.md` | 真实使用流程 + 禁止自动 propose |
| `CLAUDE.md` | 硬性规则：禁止自动 propose / [CC_TEST] / dry-run |

## 测试结果

```
352 passed in 9.32s
```

## 审阅包

`reviews/review-pack-phase-8.zip`

## 是否可以进入真实任务试用

✅ 可以。建议先用 `--dry-run` 模式熟悉审核流程，确认无误后再用 `--yes` 正式操作。

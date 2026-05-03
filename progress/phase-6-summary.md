# 阶段 6 报告 — 端到端集成测试

## 完成时间

2026-05-03

## 新增脚本

### 1. seed_demo_data.py ✅
- 幂等可重复运行
- 7 条演示数据覆盖 4 个项目
- 通过 content_hash 检测已存在，不重复插入
- 含 project/shared/global 三种 scope

### 2. dev_check.py ✅
健康检查：Python版本、目录、projects.yml、SQLite（user_version/journal_mode/foreign_keys/计数）、ConfigLoader、AppContext

### 3. run_demo_flow.py ✅
端到端演示流程：seed → list → search3次 → propose → approve → re-search → propose blocked → resolve

## 新增/更新测试

### tests/test_end_to_end.py ✅
20 个测试，三大类：
- **TestMultiProjectIsolation** (5): ERP不搜到CDR/C共享/global互见
- **TestReviewLoop** (5): propose→pending/list/approve→search/reject→not search/deprecate→not search
- **TestSecurityLoop** (5): blocked/不存原文/audit安全/source_evidence key/tags token
- **TestMCPFormat** (5): ok+data/error.code/search字段/context_pack三组/无traceback

### tests/test_multi_project.py ✅
13 个测试：
- **TestResolve** (4): workspace_path/task_description/related_files/explicit archived
- **TestCrossProjectIsolation** (7): 跨项目不互见/global互见/shared allowed/不allowed

**新增测试总计：+30**（原 290 → 320）

## 更新文件

| 文件 | 变更 |
|------|------|
| `scripts/seed_demo_data.py` | 重写：幂等演示数据填充 |
| `scripts/dev_check.py` | 新增：健康检查 |
| `scripts/run_demo_flow.py` | 新增：端到端演示流程 |
| `tests/test_end_to_end.py` | 新增：20 个端到端测试 |
| `tests/test_multi_project.py` | 重写：13 个多项目测试 |
| `README.md` | 补完整验证流程 |
| `CLAUDE.md` | 更新当前阶段 |

## 测试结果

```
320 passed in 4.97s
```

## 安全闭环验证

| 场景 | 状态 |
|------|------|
| API key → blocked/rejected | ✅ |
| memory_items 不保存私钥原文 | ✅ |
| audit_log 不保存 RSA PRIVATE KEY | ✅ |
| source_evidence key 含 API key → blocked | ✅ |
| tags 含 token → blocked | ✅ |
| blocked audit 安全摘要（无 raw key） | ✅ |

## 审阅包

`reviews/review-pack-phase-6.zip`

## 进入 Phase 7

✅ 可以。Phase 7 可选：真实 Qdrant 集成 / LLM Reviewer。

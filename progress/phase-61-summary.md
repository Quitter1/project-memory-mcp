# 阶段 6.1 报告 — 脚本收口

## 完成时间

2026-05-03

## 修复

### 1. run_demo_flow.py 直接运行 ✅
- 所有脚本统一在顶部设置 `sys.path`（项目根 + src/）
- 不再依赖 `from scripts.seed_demo_data import seed` 的包导入
- 错误响应（ok=false）时安全处理，不崩溃

### 2. 脚本支持环境变量 ✅
- seed_demo_data / dev_check / run_demo_flow 都支持 `PROJECT_MEMORY_CONFIG_DIR` / `PROJECT_MEMORY_DB_PATH`
- 未设置时默认使用项目根下 config/ + data/memory.db

### 3. dev_check.py foreign_keys 检查 ✅
- 连接后 `PRAGMA foreign_keys = ON`
- foreign_keys=1 为 OK，否则 FAIL
- journal_mode=wal 检查
- user_version>=2 检查

### 4. seed 幂等规则 ✅
- 改为按 `(project_id, scope, content_hash)` 判断
- 不同项目相同 content 不会误跳过
- 跳过不存在的项目（避免 FOREIGN KEY 约束）

### 5. tests/test_scripts.py ✅
- 5 个 subprocess 测试：seed 首次/二次跳过/dev_check 全通过/run_demo 完成
- 使用临时 config/db + 环境变量

## 测试结果

```
325 passed in 6.49s
```

| 测试文件 | 新增 | 说明 |
|----------|------|------|
| test_scripts.py | 5 (新文件) | subprocess 脚本测试 |

**新增测试总计：+5**（原 320 → 325）

## 修改文件

| 文件 | 变更 |
|------|------|
| `scripts/seed_demo_data.py` | sys.path + ENV 路径 + 幂等 (project_id,scope,hash) + 跳过不存在的项目 |
| `scripts/dev_check.py` | sys.path + ENV 路径 + FK/journal/user_version 检查 |
| `scripts/run_demo_flow.py` | sys.path + ENV 路径 + 错误响应安全处理 |
| `tests/test_scripts.py` | 新增 5 个 subprocess 测试 |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-61.zip`

## 进入 Phase 7

✅ 可以。Phase 7 可选：真实 Qdrant / LLM Reviewer。

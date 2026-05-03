# 阶段 6.4 报告 — 日志接入收口

## 完成时间

2026-05-03

## 修复

### 1. 日志真正接入 ✅
- `AppContext.__post_init__()` 自动调用 `setup_logging()`
- log_dir: `PROJECT_MEMORY_LOG_DIR` → config_dir.parent/logs
- log_level: `PROJECT_MEMORY_LOG_LEVEL` → INFO
- `setup_logging()` 幂等（`_log_initialized` 全局标志）
- 启动时记录 `app_context_start` 摘要

### 2. diagnose.py 修复 ✅
- foreign_keys = ON（连接后显式 PRAGMA）
- journal_mode = wal 检查
- user_version >= 2 检查
- log_dir 与 AppContext 一致

### 3. 日志脱敏 ✅
- `redact_sensitive()` — 14 个模式：sk-*/token/bearer/password/pwd/AKIA/私钥
- key 名保留，value 脱敏
- `_safe_param_summary()` 不记录 query/content/title 原文（仅长度）

### 4. diagnose 参数 ✅
- `--recent-errors` → 读取 errors.log 最后 50 行（脱敏）
- `--recent-audit` → 打印最近 20 条 audit_log

## 测试结果

```
339 passed in 7.02s
```

| 测试文件 | 新增 | 说明 |
|----------|------|------|
| test_logging.py | 12 (新文件) | 日志文件创建/幂等/redaction/ToolHandler 日志/敏感不进日志 |

**新增测试总计：+12**（原 327 → 339）

## 修改文件

| 文件 | 变更 |
|------|------|
| `utils/logging.py` | redact_sensitive + 幂等 setup_logging |
| `app_context.py` | __post_init__ 调用 setup_logging |
| `tools/handlers.py` | _safe_param_summary 改为仅长度 |
| `scripts/diagnose.py` | FK=ON + log_dir + --recent-errors + --recent-audit |
| `tests/test_logging.py` | 新增 12 个测试 |
| `README.md` | 日志与诊断章节 |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-64.zip`

## 进入 Phase 7

✅ 可以。Phase 7 可选：真实 Qdrant / LLM Reviewer。

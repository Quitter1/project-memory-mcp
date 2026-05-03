# 阶段 6.5 报告 — 日志接入收口（第二轮）

## 完成时间

2026-05-03

## 修复

### 1. setup_logging 重配 ✅
- 同一 log_dir 重复调用不叠加 handler
- 不同 log_dir 自动清理旧 handler 重新配置
- `_log_initialized_dir` 追踪当前目录

### 2. server.yml logging 配置 ✅
- `_init_logging()` 读取 `config/server.yml` 的 `logging` 段
- 优先级：ENV > server.yml > 默认值
- 支持 level/log_dir/file_enabled/stderr_enabled

### 3. app_context_ready ✅
- 初始化完成后记录：user_version/project_count/memory_count/audit_log_count

### 4. 异常日志脱敏 ✅
- `raw_resolve` 不再 `print(traceback)` → `logger.exception`（消息 redaction）
- `_dispatch` 只记录 `exc_type`，返回通用消息 + `request_id`
- 客户端响应不包含原始 `str(exc)`

### 5. governance_decision 默认值 ✅
- source_type 默认 `ai_inferred`
- scope 默认 `project`

### 6. diagnose.py 日志健康检查 ✅
- log_dir 不存在标记 [WARN]
- project-memory-mcp.log/errors.log 不存在标记 [WARN]

## 测试结果

```
345 passed in 6.82s
```

| 测试文件 | 新增 | 说明 |
|----------|------|------|
| test_logging.py | +6 | log_dir重配/server.yml/ready/默认值 |

**新增测试总计：+6**（原 339 → 345）

## 修改文件

| 文件 | 变更 |
|------|------|
| `utils/logging.py` | _log_initialized_dir 追踪, setup_logging 重配逻辑 |
| `app_context.py` | _init_logging(server.yml), _log_ready() |
| `tools/handlers.py` | raw_resolve logger, _dispatch 脱敏, governance 默认值 |
| `tests/test_logging.py` | +6 测试 |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-65.zip`

## 进入 Phase 7

✅ 可以。Phase 7 可选：真实 Qdrant / LLM Reviewer。

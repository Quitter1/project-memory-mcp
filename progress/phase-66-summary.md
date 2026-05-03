# 阶段 6.6 报告 — 日志接入收口（第三轮，全线清理）

## 完成时间

2026-05-03

## 修复

### 1. 全线移除 print(traceback) ✅
涉及文件：server.py + 5 个工具文件（approve/reject/deprecate/propose/search_context）
全部改为 `logging.getLogger(...)` 安全记录。

### 2. 异常响应脱敏 ✅
- GovernanceError → 稳定错误码 + redacted message
- 未知异常 → `internal_error` + 通用消息
- 不再返回 `str(exc)` 原文

### 3. logger.exception 替换 ✅
- `raw_resolve` 改用 `logger.error`（不自动附带 traceback）
- 只记录 `exc_type`，不记录完整异常消息

### 4. server.yml max_bytes/backup_count 生效 ✅
- `setup_logging()` 接收 `max_bytes`/`backup_count` 参数
- `AppContext._init_logging()` 读取 server.yml 并传入
- `RotatingFileHandler` 使用配置值

### 5. setup_logging 完整配置 key 幂等 ✅
- `_current_config` tuple：(log_dir, level, enable_file, enable_stderr, max_bytes, backup_count)
- 同配置不重配，不同配置自动重配

### 6. diagnose.py server.yml log_dir ✅
- 与 AppContext 使用同一套 log_dir 解析逻辑

### 7. 测试变量名清理 ✅
- `_log_initialized` / `_log_initialized_dir` → `_current_config`

## 测试结果

```
345 passed in 6.86s
```

## 修改文件

| 文件 | 变更 |
|------|------|
| `utils/logging.py` | _current_config 完整配置 key, max_bytes/backup_count |
| `app_context.py` | pass max_bytes/backup_count from server.yml |
| `server.py` | 移除 print(traceback), 移除 traceback import |
| `tools/approve_memory.py` | 移除 print/traceback, 使用 logger |
| `tools/reject_memory.py` | 移除 print/traceback, 使用 logger |
| `tools/deprecate_memory.py` | 移除 print/traceback, 使用 logger |
| `tools/propose_memory.py` | 移除 print/traceback, 使用 logger |
| `tools/search_context.py` | 移除 print/traceback, 使用 logger |
| `tools/handlers.py` | logger.exception → logger.error |
| `scripts/diagnose.py` | server.yml log_dir 读取 |
| `tests/test_logging.py` | 变量名清理 |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-66.zip`

## 进入 Phase 7

✅ 可以。Phase 7 可选：真实 Qdrant / LLM Reviewer。

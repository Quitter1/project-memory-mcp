# 阶段 10.5 续报 — keyword search 卡顿根因修复

## 根因诊断

日志分析确认首次 MCP 搜索卡顿 **225 秒** 不是 Qdrant 问题，而是 **keyword search** 的 SQLite 连接首次执行慢了 225 秒。

最可能原因：SQLite 锁等待 — 多个连接同时写 WAL/执行迁移时，默认无限等待。

## 修复

### 1. SQLite busy_timeout ✅
- `PRAGMA busy_timeout=5000` — 5 秒超时，不再无限等待
- 添加到 `DatabaseConnection.connect()`

### 2. KeywordSearchService 分段日志 ✅
- keyword_search_started / project_sql_done / shared_sql_done / global_sql_done / search_done
- 每段 >1000ms 输出 WARNING
- 不含 query/content 原文

### 3. keyword_search_demo.py ✅
- `--repeat N` 复现首次慢/后续快
- 三次运行均 <1ms

### 4. app_context_ready 日志修复 ✅
- 输出 qdrant_enabled/embedding_enabled/search_mode（不再写死 false）

### 5. score 显示精度 ✅
- 统一 6 位小数

## 测试结果

```
386 passed in 12.20s
keyword_search_demo: 3 runs all <1ms
```

## 修改文件

| 文件 | 变更 |
|------|------|
| `db/connection.py` | PRAGMA busy_timeout=5000 |
| `retrieval/keyword_search.py` | 分段计时日志 + WARNING |
| `app_context.py` | _log_ready 真实 qdrant/embedding/mode |
| `scripts/keyword_search_demo.py` | 新增 |
| `scripts/vector_search_demo.py` | score 6 位精度 |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-105.zip`

## 是否可以提交 Phase 10

✅ 可以。

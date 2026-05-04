# 阶段 10.6 报告 — vector search 硬超时修复

## 完成时间

2026-05-04

## 根因确认

日志分析确认首次 MCP 搜索卡 163 秒是 **vector search 线程阻塞**，不是 keyword。

修复后：首次 ~1000ms，后续 31-47ms。

## 修复

### 1. ThreadPoolExecutor 硬超时 ✅
- `future.result(timeout=vector_timeout_seconds)` 真正中断等待
- 超时后取消 future，fallback keyword
- `_vector_executor` 复用（非每次创建）

### 2. vector_cooldown ✅
- 超时后 60 秒内跳过 vector，直接 keyword fallback
- `fallback_reason=vector_cooldown`

### 3. QdrantClient prefer_grpc=False ✅
- 已明确设置，优先 HTTP

### 4. 分段 vector 日志 ✅
- vector_started / embed_done / qdrant_query_done / vector_worker_done / vector_timeout

### 5. 脚本补强 ✅
- `search_context_demo.py --repeat N`
- `mcp_search_smoke.py --repeat N`

## 验证结果

```
search_context_demo --repeat 3: 1000ms → 31ms → 31ms
mcp_search_smoke --repeat 3: 1031ms → 46ms → 47ms
pytest: 386 passed
```

## 修改文件

| 文件 | 变更 |
|------|------|
| `retrieval/search.py` | ThreadPoolExecutor + future.result(timeout) + cooldown + 分段日志 |
| `db/connection.py` | PRAGMA busy_timeout=5000 |
| `scripts/search_context_demo.py` | --repeat |
| `scripts/mcp_search_smoke.py` | 新增 |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-106.zip`

## 是否可以提交 Phase 10

✅ 可以。

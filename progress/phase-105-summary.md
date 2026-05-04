# 阶段 10.5 报告 — 搜索超时保护 + 耗时日志

## 完成时间

2026-05-04

## 修复

### 1. max_search_seconds + fallback_reason ✅
- `search.max_search_seconds=8`：超时自动 fallback keyword
- `search.vector_timeout_seconds=3`：Qdrant 单次调用超时
- `SearchResultSet.fallback_reason`：vector_timeout / vector_error

### 2. tool started/done 耗时日志 ✅
- `_dispatch()` 记录 tool_started/tool_done，含 elapsed_ms
- 只记 query_len/project_id/counts，不记原文

### 3. search_context_demo.py ✅
- 直接调用 search_service，输出完整 metadata
- search_method/fallback_reason/keyword_count/vector_count/hybrid_count/elapsed_ms

### 4. check_qdrant.py --warmup ✅
- count + query_points 首次预热
- 超 3s 输出 WARN

### 5. min_vector_score 过滤确认 ✅
- `_vector_hits_to_items()` score < min_vector_score 直接跳过
- demo/正式 search 统一使用

## 测试结果

```
386 passed in 12.04s
```

## 修改文件

| 文件 | 变更 |
|------|------|
| `retrieval/search.py` | max_search_seconds/fallback_reason/TimeoutError |
| `models/search_result.py` | fallback_reason 字段 |
| `tools/handlers.py` | tool_started/tool_done 耗时日志 |
| `scripts/search_context_demo.py` | 新增 |
| `scripts/check_qdrant.py` | --warmup |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-105.zip`

## 是否可以提交 Phase 10

✅ 可以。

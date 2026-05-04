# 阶段 10.4 报告 — vector 权限过滤 + 诊断收口

## 完成时间

2026-05-04

## 修复

### 1. vector hit 权限过滤一致性 ✅
- `_vector_hits_to_items()` 新增共享/全局权限过滤
- shared allowed_projects/denied_projects 过滤
- include_shared/include_global/include_candidates 过滤
- modules/types/tags/min_confidence 过滤
- min_vector_score 阈值过滤
- rejected/deprecated/superseded/conflict 状态过滤

### 2. min_vector_score ✅
- `search.min_vector_score: 0.001`（config/server.yml）
- score < 阈值直接跳过

### 3. vector_search_demo 精确对比 ✅
- [keyword] 段使用原始 `KeywordSearchService`
- [vector] 段使用 `QdrantVectorStore`
- [hybrid] 段合并结果

### 4. embedding.enabled=true ✅
- config/server.yml 明确启用

### 5. 搜索耗时日志 ✅
- search_started / keyword_done / vector_done / search_done
- 只记录 query_len、counts、elapsed_ms

## 测试结果

```
386 passed in 11.99s
```

## 修改文件

| 文件 | 变更 |
|------|------|
| `retrieval/search.py` | 完整权限过滤 + 耗时日志 + min_vector_score |
| `config/server.yml` | embedding.enabled=true, min_vector_score |
| `scripts/vector_search_demo.py` | 纯 keyword search 段 |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-104.zip`

## 是否可以提交 Phase 10

✅ 可以。

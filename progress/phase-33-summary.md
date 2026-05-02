# 阶段 3.3 修复报告

## 完成时间

2026-05-02

## 修复项

### shared/global 硬编码 limit=20 修复 ✅
- `_search_shared_scope()` 增加 `limit` 参数
- `_search_global_scope()` 增加 `limit` 参数
- `search()` 使用 `internal_limit = max(max_results * 3, 50)`
- 最终截断仍由 `KnowledgeSearchService` 统一执行

### 文档 ✅
- CLAUDE.md commit 示例改为按阶段命名

## 测试结果

```
123 passed in 1.94s
```

| 新增 | 测试 | 说明 |
|------|------|------|
| test_40 | shared 60 条 max_results=50 → 返回 50 | shared 大结果不截断 |
| test_41 | global 60 条 max_results=50 → 返回 50 | global 大结果不截断 |

## 修改文件

| 文件 | 修复 |
|------|------|
| `retrieval/keyword_search.py` | shared/global scope 增加 limit 参数 |
| `CLAUDE.md` | commit 示例更新 |
| `tests/test_search.py` | +2 测试 |

## 审阅包

`reviews/review-pack-phase-33.zip`

## 进入 Phase 4

✅ 可以。

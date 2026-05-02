# 阶段 3.1 修复报告

## 完成时间

2026-05-02

## 修复项

### 1. max_results 全局限制 ✅
- 全局截断：`limited = merged[:max_results]` → 再构建 context_pack
- `SearchResultSet` 新增 `total_returned` 字段
- `total_found` = 截断前命中数，`total_returned` = 实际返回数

### 2. source_evidence 丢失修复 ✅
- `_rows_to_results` 解析 `source_evidence` JSON
- `source_file`/`source_line` 自动补入 evidence
- 解析失败返回 `{}`，不影响搜索

### 3. 空 query 过滤失效修复 ✅
- `search_empty()` 接收 modules/types/tags/min_confidence
- 空 query 仍遵守全部过滤规则

### 4. shared/global 提前截断修复 ✅
- `KeywordSearchService.search()` 不再做 `[:max_results]` 截断
- 统一由 `KnowledgeSearchService` 在 merge 后截断

### 5. JSON membership instr 替代 LIKE ✅
- shared filter 使用 `instr()` 替代 `LIKE`
- 避免 `_` 被 LIKE 当通配符误判

### 6. 审阅包脚本编码 ✅
- 新增 `PYTHONUTF8=1`

## 测试结果

```
115 passed in 1.67s
```

| 新增测试类 | 测试数 | 说明 |
|-----------|--------|------|
| TestGlobalMaxResults | 3 | 全局截断，total_found/returned 一致性 |
| TestSourceEvidence | 2 | evidence 解析 + file/line 补充 |
| TestEmptyQueryFilters | 4 | module/type/tag/confidence 空 query 过滤 |
| TestInstrMembership | 2 | 下划线精确匹配 + 通配符防误判 |
| TestScopeNotPreempted | 2 | shared/global 不被 project 挤掉 |

## 修改文件

| 文件 | 修复 |
|------|------|
| `models/search_result.py` | 新增 `total_returned` |
| `retrieval/search.py` | 全局截断 + total_found/total_returned |
| `retrieval/keyword_search.py` | 去内部截断 + search_empty 全参数 + source_evidence 解析 |
| `retrieval/filter_builder.py` | instr 替代 LIKE |
| `scripts/make_review_pack.py` | PYTHONUTF8=1 |
| `tests/test_search.py` | +13 测试 |

## 审阅包

`reviews/review-pack-phase-31.zip`

## 进入 Phase 4

✅ 可以。

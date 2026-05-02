# 阶段 3.2 修复报告

## 完成时间

2026-05-02

## 修复项

### 1. tag 过滤进 SQL ✅
- FilterBuilder 三个过滤方法支持 `tags` 参数，使用 `EXISTS + IN` 子查询
- 移除 Python 层的 `if tags:` 过滤，避免 LIMIT 截断导致 tag 数据丢失
- 空 query 和非空 query 均支持 tag SQL 过滤

### 2. LIKE 转义 ✅
- `escape_like()` 转义 `%`、`_`、`\`
- 所有 LIKE 使用 `ESCAPE '\'` 子句
- `like_pattern()` 和 `like_clause()` 统一 helper

### 3. 复用 ResultRanker ✅
- `search.py` 移除手写 context_pack 构造
- 统一使用 `self.ranker.build_context_pack()`

### 4. 文档 ✅
- CLAUDE.md 新增审阅规则（5 项输出）+ commit 提醒

## 测试结果

```
121 passed in 1.86s
```

| 新增类 | 测试数 | 说明 |
|--------|--------|------|
| TestTagSqlFiltering | 2 | rare tag 不被 LIMIT 截断丢失 |
| TestLikeEscape | 4 | %/_ 转义 + 真实 %/_ 匹配 |

## 修改文件

| 文件 | 修复 |
|------|------|
| `CLAUDE.md` | 审阅规则 + commit 提醒 |
| `retrieval/filter_builder.py` | tag 进 SQL + _optional_filters 移除 tags |
| `retrieval/keyword_search.py` | LIKE 转义 + 去 Python tag 过滤 + 去内部截断 |
| `retrieval/search.py` | 复用 ResultRanker.build_context_pack |
| `tests/test_search.py` | +6 测试 |

## 审阅包

`reviews/review-pack-phase-32.zip`

## 进入 Phase 4

✅ 可以。建议执行：
```bash
git add .
git commit -m "phase 0-3.2 search foundation"
```

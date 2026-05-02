# 阶段 2.7 修复报告

## 完成时间

2026-05-02

## 修复项

### 1. ConfigLoader 校验 defaults + 合并后配置 ✅
- 新增 `_validate_defaults()` 方法
- `_is_number()` / `_is_integer()` helper 显式排除 bool
- 错误信息带字段路径（`defaults.knowledge_policy.xxx`, `project[id].xxx`）
- 合并后的 ProjectConfig 类型正确

### 2. migration v2 — 唯一约束 ✅
- `LATEST_VERSION` → 2
- 新增 migration v2：先去重再加唯一索引
- `idx_tags_unique` / `idx_relations_unique`

### 3. 修复 or 默认值覆盖合法 0 ✅
- `project_repo.py` 4 处修复
- `memory_repo.py` 1 处修复
- `row["field"] or default` → `row["field"] if row["field"] is not None else default`

### 4. 文档 + 审阅包 ✅
- `phase-26-summary.md` / `phase-27-summary.md`
- `make_review_pack.py` 在打包前检查 summary 存在
- CLAUDE.md 新增 changed_files 路径规则 + 小数阶段编号约定

## 测试结果

```
82 passed in 1.07s
```

| 文件 | 测试数 |
|------|--------|
| test_sqlite_migrations.py | 14 (+3) |
| test_memory_repo.py | 27 (+4) |
| test_config_loader.py | 22 (+7) |
| test_resolver.py | 19 (不变) |

## 新增测试（14 个）

| # | 场景 | 文件 |
|---|------|------|
| 1 | defaults.auto_approve 字符串报错 | config_loader |
| 2 | defaults.allow_ai 字符串报错 | config_loader |
| 3 | project.auto_approve bool 报错 | config_loader |
| 4 | project.max_candidate bool 报错 | config_loader |
| 5 | defaults.risk_threshold 非法 | config_loader |
| 6 | defaults.forbidden_types 非 list | config_loader |
| 7 | 合并后类型正确 | config_loader |
| 8 | schema version == 2 | sqlite_migrations |
| 9 | migration v2 重复不报错 | sqlite_migrations |
| 10 | 唯一索引存在 | sqlite_migrations |
| 11 | 重复 add_tag 只保留一条 | memory_repo |
| 12 | 重复 add_relation 只保留一条 | memory_repo |
| 13 | auto_approve_threshold=0 读回 0 | memory_repo |
| 14 | confidence=0 读回 0 | memory_repo |

## 修改文件清单

| 文件 | 操作 |
|------|------|
| `config/loader.py` | _validate_defaults, _is_number, _is_integer, 错误信息带路径 |
| `db/migrations.py` | LATEST_VERSION=2, migration v2 |
| `db/project_repo.py` | 4 处 or → is not None |
| `db/memory_repo.py` | 1 处 or → is not None |
| `scripts/make_review_pack.py` | 检查 summary 存在 |
| `CLAUDE.md` | changed_files 规则 + 阶段编号约定 |
| `progress/phase-26-summary.md` | 新建 |
| `progress/phase-27-summary.md` | 新建（本文件） |
| `tests/test_config_loader.py` | +7 defaults 校验测试 |
| `tests/test_memory_repo.py` | +4 测试 |
| `tests/test_sqlite_migrations.py` | +3 migration v2 测试 |

## 是否可以进入 Phase 3

✅ **是**。Phase 0-2.7 基础层全部修复通过。

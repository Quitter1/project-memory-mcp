# 阶段 2.6 修复报告

## 完成时间

2026-05-02

## 修复项

### 1. ConfigLoader 字段校验 ✅

**问题**：只校验 name/slug，太弱。

**修复**：新增 `_validate_project()` 方法，校验 14 个字段：
- status、root_paths、path_patterns、aliases、tech_stack_keywords、module_keywords
- default_confidence、auto_approve_threshold、max_candidate_per_task、retention_days
- allow_ai_auto_approve、forbidden_auto_types、risk_threshold_for_review、require_review_if_conflict

**新测试**（7 个）：test_09~test_15

### 2. tags/relations 时间格式 ISO UTC ✅

**问题**：SQLite `datetime('now')` 输出 `YYYY-MM-DD HH:MM:SS`，未使用 ISO UTC。

**修复**：`add_tag()` 和 `add_relation()` 显式写入 Python UTC ISO 时间。

**新测试**（2 个）：test_22_tag_created_at_iso_utc、test_23_relation_created_at_iso_utc

### 3. Windows 路径大小写跨平台 ✅

**问题**：只在 `os.name == "nt"` 时才小写，非 Windows 系统无法处理盘符路径。

**修复**：新增 `_is_windows_drive_path()` 检测盘符模式（X:/ 或 X:\），无论系统都小写。

**新测试**（1 个）：test_19_windows_path_case_insensitive_always

### 4. 文档更新 ✅
- CLAUDE.md：阶段状态 → 2.6，新增 tag/relation 方法边界说明
- `.gitignore`：新增 `reviews/`

### 5. 审阅包管理 ✅
- `scripts/make_review_pack.py`：输出到 `reviews/` 目录，已有同名 zip 时移到 `reviews/backups/`
- 历史审阅包已移到 `reviews/backups/`

## 测试结果

```
68 passed in 0.80s
```

| 文件 | 测试数 |
|------|--------|
| test_sqlite_migrations.py | 11 |
| test_memory_repo.py | 23 |
| test_config_loader.py | 15 |
| test_resolver.py | 19 |

## 新增测试清单（共 10 个）

| # | 文件 | 测试 | 场景 |
|---|------|------|------|
| 1 | config_loader | test_09 | invalid status 报错 |
| 2 | config_loader | test_10 | root_paths 不是 list 报错 |
| 3 | config_loader | test_11 | aliases 不是 list 报错 |
| 4 | config_loader | test_12 | auto_approve 不是数字报错 |
| 5 | config_loader | test_13 | max_candidate 不是整数报错 |
| 6 | config_loader | test_14 | risk_threshold 非法报错 |
| 7 | config_loader | test_15 | allow_ai_auto 不是 bool 报错 |
| 8 | memory_repo | test_22 | tag created_at 含 T+Z |
| 9 | memory_repo | test_23 | relation created_at 含 T+Z |
| 10 | resolver | test_19 | 跨平台盘符路径小写 |

## 修改文件清单

| 文件 | 操作 |
|------|------|
| `config/loader.py` | 新增 `_validate_project()` 14 字段校验 |
| `db/memory_repo.py` | add_tag/add_relation 写入 ISO UTC 时间 |
| `project/resolver.py` | `_normalize_path` 盘符跨平台 + `_is_windows_drive_path` |
| `scripts/make_review_pack.py` | 输出到 reviews/ + 自动备份旧 zip |
| `CLAUDE.md` | 阶段状态 2.6 + tag/relation 边界 |
| `.gitignore` | 新增 `reviews/` |
| `tests/test_config_loader.py` | +7 校验测试 |
| `tests/test_memory_repo.py` | +2 时间格式测试 |
| `tests/test_resolver.py` | +1 跨平台路径测试 |

## 审阅包

`reviews/review-pack-phase-26.zip` (103 文件)

历史包：`reviews/backups/review-pack-phase-25.zip`

## 是否可以进入 Phase 3

✅ **是**。Phase 0-2.6 全部修复和测试通过。

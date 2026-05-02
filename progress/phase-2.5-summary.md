# 阶段 2.5 修复报告

## 完成时间

2026-05-02

## 修复清单

### 1. ProjectRepository audit 事务 ✅

**问题**：upsert_project/update_status 中 commit 在 audit_log 之前，两者不在同一事务。

**修复**：commit 移到 get_by_id + audit.log_action 之后。

**文件**：`db/project_repo.py`

**新测试**：
- test_17_project_audit_persisted_after_reopen — 关闭连接后重新打开，project 和 audit_log 均存在
- test_18_project_update_status_audit_persisted_after_reopen — 同上，验证 update_status 场景

### 2. Resolver 兼容 ProjectConfig 和 Project ✅

**问题**：resolver 直接使用 `project.recognition.root_paths`，只兼容 ProjectConfig。

**修复**：新增兼容性 helper 方法 — `_get_root_paths`, `_get_aliases`, `_get_tech_keywords`, `_get_module_keywords`, `_get_project_status`, `_project_to_dict`（实例方法）

**文件**：`project/resolver.py`

**新测试**：
- test_15_resolver_with_sqlite_repo — SQLite ProjectRepository 初始化后识别正常
- test_16_archived_sqlite_with_warning — archived 项目显式识别返回 warning

### 3. Resolver ambiguous 路径匹配 ✅

**问题**：workspace_path/changed_files 匹配多个项目时，结果被跳过，继续往下走到 unable_to_resolve。

**修复**：`result.resolved and not result.ambiguous` → `result.resolved`（ambiguous 也直接返回）

**文件**：`project/resolver.py`

**新测试**：
- test_17_two_active_projects_same_root_ambiguous — 两项目同 root_path，workspace_path → ambiguous
- test_18_two_active_projects_same_root_files_ambiguous — 同上 changed_files → ambiguous

### 4. MemoryItem tags 返回丢失 ✅

**问题**：`_row_to_memory_item` 和 `_load_tags_from_row` 读取不存在的 `tags` 列，memory_tags 表数据未加载。

**修复**：`_row_to_memory_item` 改为实例方法，从 memory_tags 表查询标签。

**文件**：`db/memory_repo.py`

**新测试**：
- test_19_tags_in_create_memory — create 返回 tags
- test_20_tags_in_get_by_id — get_by_id 返回 tags
- test_21_tags_in_list_memories — list 返回 tags

### 5. make_review_pack.py ✅

**修复**：
- subprocess.run 检查 returncode
- 测试失败时不生成 zip，exit 1
- 使用 shell=True（Windows 兼容）
- PYTHONIOENCODING=utf-8
- 排除 *.egg-info/, .pytest_cache/
- 包含 .gitignore
- 空 git diff 时写说明文字
- 自测：故意失败命令 → exit 1，不生成 zip

### 6. 清理生成物 ✅

- 删除 `src/project_memory_mcp.egg-info/`
- 删除 `.pytest_cache/`
- 删除所有 `__pycache__/` 和 `*.pyc`
- 更新 `.gitignore`：新增 `src/*.egg-info/`, `review-pack-*.zip`

## 测试结果

```
58 passed in 0.73s
```

| 文件 | 测试数 | 变化 |
|------|--------|------|
| test_sqlite_migrations.py | 11 | 不变 |
| test_memory_repo.py | 21 | +5 (audit 2 + tags 3) |
| test_config_loader.py | 8 | 不变 |
| test_resolver.py | 18 | +4 (sqlite 2 + ambiguous 2) |

## 修改文件清单

| 文件 | 操作 |
|------|------|
| `db/project_repo.py` | 修复事务（commit 移到 audit 之后） |
| `db/memory_repo.py` | 修复 tags 加载（实例方法 + 查 memory_tags） |
| `project/resolver.py` | 兼容 Project + 修复 ambiguous |
| `scripts/make_review_pack.py` | 完全重写（测试失败拦截 + 编码 + 排除） |
| `.gitignore` | 新增 `src/*.egg-info/`, `review-pack-*.zip` |
| `tests/test_memory_repo.py` | +5 测试 |
| `tests/test_resolver.py` | +4 测试 |

## 审阅包

`review-pack-phase-25.zip` (98 文件)

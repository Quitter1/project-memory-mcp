# 阶段 6.2 报告 — 脚本收口（清理）

## 完成时间

2026-05-03

## 修复

### 1. 统一 scripts/_paths.py ✅
- `_paths.py` 提供 `ensure_import_paths()` + `get_project_paths()`
- seed_demo_data / dev_check / run_demo_flow 全部改用 `import _paths`
- 三个脚本不再各自定义 `_get_paths()` 和 sys.path 逻辑

### 2. pytest 插件禁用说明 ✅
- README.md 增加 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 用法
- 含 Linux/macOS 和 Windows PowerShell 示例

## 测试结果

```
325 passed in 6.27s
```

## 修改文件

| 文件 | 变更 |
|------|------|
| `scripts/_paths.py` | 重写：ensure_import_paths() + get_project_paths() |
| `scripts/seed_demo_data.py` | 使用 _paths，移除重复逻辑 |
| `scripts/dev_check.py` | 使用 _paths，移除重复逻辑 |
| `scripts/run_demo_flow.py` | 使用 _paths，移除重复逻辑 |
| `README.md` | 增加 pytest 插件禁用说明 |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-62.zip`

## 进入 Phase 7

✅ 可以。Phase 7 可选：真实 Qdrant / LLM Reviewer。

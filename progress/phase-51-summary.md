# 阶段 5.1 报告 — MCP 封装层收口

## 完成时间

2026-05-03

## 修复

### 1. server.py 可测试性 ✅
- `create_server(ctx=None)` 支持传入已有 AppContext
- 测试时不依赖真实 config/data 目录
- `tests/test_mcp_server.py` 验证 9 个 tool 名称

### 2. 配置路径环境变量 ✅
优先级：
- `PROJECT_MEMORY_CONFIG_DIR` → `cwd/config` → 源码相对 fallback
- `PROJECT_MEMORY_DB_PATH` → `cwd/data/memory.db`

### 3. project_id 校验 ✅
- `search_project_context` → 不存在返回 `project_not_found`
- `list_memories` → 不存在返回 `project_not_found`
- `propose_memory` / `get_project_profile` — 已存在，确认正确

### 4. resolve 错误码修复 ✅
- 显式 project_id 不存在 → `project_not_found`（而非 `project_id_required`）
- 附带 `suggest_projects` 列表

### 5. 错误码分类 ✅
- `GovernanceError` → `memory_not_found` / `invalid_state` / `invalid_params`
- `ValueError`/`TypeError` → `invalid_params`
- 未知异常 → `governance_error`（traceback 仅写 stderr）

### 6. tools/*.py 方案 A 实现 ✅
9 个工具文件全部实现 `handle(ctx, params) -> dict`：
- `list_projects.py` / `resolve_project.py` / `get_project_profile.py`
- `search_context.py` / `propose_memory.py` / `list_memories.py`
- `approve_memory.py` / `reject_memory.py` / `deprecate_memory.py`
- `handlers.py` 精简为委托层 + 统一错误包装 + resolve helper

### 7. review-pack sandbox/ ✅
- `make_review_pack.py` allowed_tops 增加 `sandbox`

### 8. AppContext.sync_projects 返回值 ✅
- 改为 `created + updated`（均为整数）

### 9. task_description / related_files 支持 ✅
- `search_project_context` / `propose_memory` 透传这两个参数到 resolve helper

## 测试结果

```
279 passed in 4.22s
```

| 测试文件 | 新增 | 说明 |
|----------|------|------|
| test_mcp_server.py | 11 (新文件) | server 可测性/配置路径/错误码/task_description |
| test_mcp_tools.py | 0 (修 2 错误码断言) | 适配新错误码 |

**新增测试总计：+11**（原 268 → 279）

## 修改文件

| 文件 | 变更 |
|------|------|
| `server.py` | ctx 参数 + ENV 配置路径 + task_description/related_files |
| `tools/handlers.py` | 精简为委托层, resolve 错误码区分 |
| `tools/list_projects.py` | 实现 handle() |
| `tools/resolve_project.py` | 实现 handle() |
| `tools/get_project_profile.py` | 实现 handle() |
| `tools/search_context.py` | 实现 handle() + project_id 校验 + resolve 触发 |
| `tools/propose_memory.py` | 实现 handle() + 错误码分类 + resolve 触发 |
| `tools/list_memories.py` | 实现 handle() + project_id 校验 |
| `tools/approve_memory.py` | 实现 handle() + 错误码分类 |
| `tools/reject_memory.py` | 实现 handle() + 错误码分类 |
| `tools/deprecate_memory.py` | 实现 handle() + 错误码分类 |
| `app_context.py` | sync_projects 返回值修复 |
| `scripts/make_review_pack.py` | 加入 sandbox |
| `tests/test_mcp_server.py` | 新增 11 测试 |
| `tests/test_mcp_tools.py` | 适配错误码变更 |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-51.zip`

## 进入 Phase 6

✅ 可以。Phase 6 为多项目集成测试 + 演示数据。

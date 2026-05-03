# 阶段 5.3 报告 — MCP 封装层收口（第三轮）

## 完成时间

2026-05-03

## 修复

### 1. mcp 缺失测试 skip ✅
- `test_create_server_with_ctx` / `test_create_server_skip_without_mcp` 使用 `pytest.importorskip("mcp.server.fastmcp")`
- 未安装 mcp 时 skip 而非 fail
- 路径解析测试独立于 mcp

### 2. 单 ENV 路径同源 ✅
- 只设 `PROJECT_MEMORY_CONFIG_DIR` → db 跟随 config 所在项目根
- 只设 `PROJECT_MEMORY_DB_PATH` → config 跟随 db 所在项目根
- 两个都设 → 各自使用显式值
- 都没设 → cwd/config 优先，否则源码根 fallback

### 3. resolve_project 精确测试 ✅
- `explicit_id` → `match_method == "explicit_id"`
- `workspace_path` → `match_method == "workspace_path"`

### 4. docs/mcp-tools.md 错误格式 ✅
- 成功格式 `{"ok": true, "data": {}}`
- 错误格式 `{"ok": false, "error": {"code": "...", "message": "...", "details": {}}}`
- 补常见错误码表

### 5. sandbox 文件说明 ✅
- 文件名引用更新为 `test_tool_handler_client.py`
- 说明不是真实 MCP stdio 客户端

### 6. 旧测试宽松断言收紧 ✅
- `test_resolve_not_found` 从 `in ("project_not_found", "project_id_required")` → `== "project_not_found"`

## 测试结果

```
290 passed in 4.11s
```

| 测试文件 | 变化 | 说明 |
|----------|------|------|
| test_mcp_server.py | +4 测试, 收紧 2 个 | 单ENV同源 + resolve精确 + importorskip |
| test_mcp_tools.py | 收紧 1 个断言 | project_not_found 精确 |

**新增测试总计：+4**（原 286 → 290）

## 修改文件

| 文件 | 变更 |
|------|------|
| `server.py` | 单ENV路径同源逻辑 |
| `tests/test_mcp_server.py` | importorskip + 单ENV测试 + resolve精确 |
| `tests/test_mcp_tools.py` | 收紧 resolve 断言 |
| `docs/mcp-tools.md` | 错误/成功格式 + 错误码表 |
| `sandbox/test_tool_handler_client.py` | 文件名 + 说明更新 |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-53.zip`

## 进入 Phase 6

✅ 可以。Phase 6 为端到端多项目集成测试 + 演示数据。

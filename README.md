# Project Memory MCP

MCP 服务，为 Claude Code、Codex、Cursor 等任务型 AI 提供**项目长期记忆能力**。

不是简单的向量数据库查询工具，而是**项目知识治理服务**。

## 已实现能力

- SQLite 主存储（WAL 模式）
- 多项目配置（YAML → SQLite 同步）
- ProjectResolver 多策略项目识别
- keyword-first search + context_pack 输出
- 知识治理：敏感信息检测 / 去重 / 双状态机 / 多因素审批
- blocked 级敏感信息不保存原文
- audit_log 安全摘要
- MCP 9 tools（FastMCP v1.27.0）

## 快速开始

```bash
# 安装
pip install -e ".[dev]"

# 初始化数据库 + 同步项目
python scripts/init_db.py
python scripts/sync_projects.py

# 运行测试
python -m pytest tests/ -v

# 启动 MCP server（stdio）
python -m project_memory_mcp
```

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `PROJECT_MEMORY_CONFIG_DIR` | 配置目录（含 projects.yml） | cwd/config 或源码根/config |
| `PROJECT_MEMORY_DB_PATH` | SQLite 数据库路径 | cwd/data/memory.db |

## Claude Code 接入示例

```json
{
  "mcpServers": {
    "project-memory-mcp": {
      "command": "python",
      "args": ["-m", "project_memory_mcp"],
      "env": {
        "PROJECT_MEMORY_CONFIG_DIR": "F:/project/project-memory-mcp/config",
        "PROJECT_MEMORY_DB_PATH": "F:/project/project-memory-mcp/data/memory.db"
      }
    }
  }
}
```

## MCP 工具清单

| 工具 | 分类 | 说明 |
|------|------|------|
| `list_projects` | 查询 | 列出已配置项目 |
| `resolve_project` | 识别 | 多策略项目识别 |
| `get_project_profile` | 查询 | 项目配置 + 统计 |
| `search_project_context` | 检索 | 搜索知识返回 context_pack |
| `propose_memory` | 写入 | 提交候选知识走治理流程 |
| `list_memories` | 查询 | 列出知识条目 |
| `approve_memory` | 治理 | 审核通过 |
| `reject_memory` | 治理 | 审核拒绝 |
| `deprecate_memory` | 治理 | 废弃 |

## 开发阶段

| 阶段 | 状态 |
|------|------|
| Phase 0~3 | 脚手架 + SQLite + 配置 + 检索 |
| Phase 4~4.4 | 知识治理 + 安全收口 |
| Phase 5~5.2 | MCP 工具 + 封装层收口 |
| Phase 6 | 端到端集成测试（完成） |

## 本地完整验证

```bash
# 1. 环境检查
python scripts/dev_check.py

# 2. 初始化 + 同步
python scripts/init_db.py
python scripts/sync_projects.py

# 3. 演示数据（幂等可重跑）
python scripts/seed_demo_data.py

# 4. 端到端演示流程
python scripts/run_demo_flow.py

# 5. 全量测试
python -m pytest tests/ -v

# 如果本机 pytest 插件较多，脚本 subprocess 测试可能卡住，可用：
# Linux/macOS:
#   PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/ -v
# Windows PowerShell:
#   $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"
#   python -m pytest tests/ -v
#   Remove-Item Env:\PYTEST_DISABLE_PLUGIN_AUTOLOAD
```

## 备注

- Qdrant 向量检索尚未启用（keyword search 可用）
- LLM Reviewer 尚未启用（rule-based reviewer 可用）
- `sandbox/test_tool_handler_client.py` 是 ToolHandler 级调试客户端，不是真实 MCP stdio 客户端

## 许可

MIT

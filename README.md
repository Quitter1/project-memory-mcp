# Project Memory MCP

MCP 服务，为 Claude Code、Codex、Cursor 等任务型 AI 提供**项目长期记忆能力**。

## 核心能力

| 模块 | 说明 |
|------|------|
| SQLite 主存储 | WAL 模式，唯一事实源 |
| 多项目配置 | YAML → SQLite 同步，多项目隔离 |
| ProjectResolver | 多策略项目识别（workspace_path/files/task_description） |
| Keyword search | SQLite LIKE，保底可用 |
| Qdrant hybrid search | 向量 + 关键词混合检索，BGE-M3 1024-dim |
| 知识治理 | 敏感检测 → 去重 → 双状态机 → 多因素审批 |
| blocked 级 | 私钥/token/密码不保存原文，仅写审计日志 |
| audit_log | 安全摘要，不含敏感原文 |
| MCP 9 tools | FastMCP v1.27.0 stdio |
| LLM Reviewer | 二次评审（默认关闭，环境变量启用） |
| 检索评测 | eval_search 命中率/首位准确率 |

## 快速开始

```bash
# 安装
pip install -e ".[dev]"

# 空库初始化（复制 example 配置 → 创建 memory.db）
python scripts/bootstrap_empty.py

# 运行测试
python -m pytest tests/ -v

# 启动 MCP server（stdio）
python -m project_memory_mcp
```

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `PROJECT_MEMORY_CONFIG_DIR` | 配置目录 | cwd/config |
| `PROJECT_MEMORY_DB_PATH` | 数据库路径 | cwd/data/memory.db |
| `PROJECT_MEMORY_LOG_DIR` | 日志目录 | config_dir.parent/logs |
| `PROJECT_MEMORY_LOG_LEVEL` | 日志等级 | INFO |
| `PROJECT_MEMORY_LLM_API_KEY` | LLM Reviewer API Key | 无 |
| `PROJECT_MEMORY_LLM_BASE_URL` | LLM Base URL | 无 |
| `PROJECT_MEMORY_LLM_MODEL` | LLM 模型名 | 无 |
| `PROJECT_MEMORY_LLM_REVIEWER_ENABLED` | 启用 LLM Reviewer | 0 |

## MCP 工具清单

| 工具 | 分类 | 说明 |
|------|------|------|
| `list_projects` | 查询 | 列出已配置项目 |
| `resolve_project` | 识别 | 多策略项目识别 |
| `get_project_profile` | 查询 | 项目配置 + 统计 |
| `search_project_context` | 检索 | hybrid 搜索返回 context_pack |
| `propose_memory` | 写入 | 提交候选知识走治理流程 |
| `list_memories` | 查询 | 列出知识条目 |
| `approve_memory` | 治理 | 审核通过 |
| `reject_memory` | 治理 | 审核拒绝 |
| `deprecate_memory` | 治理 | 废弃 |

## Claude Code 接入

```json
{
  "mcpServers": {
    "project-memory-mcp": {
      "command": "F:/project/project-memory-mcp/.venv/Scripts/python.exe",
      "args": ["-m", "project_memory_mcp"],
      "env": {
        "PROJECT_MEMORY_CONFIG_DIR": "F:/project/project-memory-mcp/config",
        "PROJECT_MEMORY_DB_PATH": "F:/project/project-memory-mcp/data/memory.db",
        "PROJECT_MEMORY_LOG_DIR": "F:/project/project-memory-mcp/logs",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

详细：`docs/ClaudeCode接入配置.md`

## 运维命令

```bash
# ── 初始化 ──
python scripts/bootstrap_empty.py          # 空库初始化
python scripts/dev_check.py                # 环境检查
python scripts/seed_demo_data.py           # 演示数据（幂等）
python scripts/run_demo_flow.py            # 端到端演示

# ── 诊断 ──
python scripts/diagnose.py                 # 综合诊断
python scripts/diagnose.py --vector-summary   # 向量索引状态
python scripts/diagnose.py --review-summary   # 审核摘要
python scripts/diagnose.py --llm-summary      # LLM Reviewer 状态

# ── 检索评测 ──
python scripts/eval_search.py --mode hybrid   # 评测命中率
python scripts/vector_search_demo.py --project rpa-electron --query "..."
python scripts/search_context_demo.py --project rpa-electron --query "..." --repeat 3

# ── 审核 ──
python scripts/review_memories.py list --status pending_review
python scripts/review_memories.py show --id <memory_id>
python scripts/review_memories.py approve --id <memory_id> --comment "确认" --yes
python scripts/review_memories.py reject --id <memory_id> --reason "..." --yes

# ── 清理 ──
python scripts/cleanup_test_memories.py --dry-run
python scripts/cleanup_test_memories.py --reject --yes
```

## PowerShell 运维

```powershell
# 健康检查
powershell -File scripts/ops/health_check.ps1

# 备份 memory.db + config
powershell -File scripts/ops/backup_memory_db.ps1

# 停止 MCP 进程
powershell -File scripts/kill_mcp_processes.ps1 -Kill

# 端到端验收
powershell -File scripts/ops/e2e_usage_check.ps1
```

## 部署

- 源码部署空库：`docs/source-deployment.md`
- 部署指南：`docs/部署指南.md`
- 正式使用检查清单：`docs/正式使用检查清单.md`

## 真实使用流程

1. 任务开始：`search_project_context`（自动检索）
2. 任务结束：先列候选，**不自动写入**
3. 用户确认：`propose_memory`（逐条提交）
4. 人工审核：`python scripts/review_memories.py list --status pending_review`
5. 测试清理：`python scripts/cleanup_test_memories.py --dry-run`

详细：`docs/ClaudeCode记忆工作流.md`、`docs/Agent使用规范.md`

## 核心规则

- **AI 默认不允许自动 propose_memory**，必须用户明确要求
- 测试知识必须以 `[CC_TEST]` 开头
- 所有写入操作必须可审计（走 governance）
- **API Key 只能通过环境变量，绝不写入任何文件**
- SQLite 是唯一事实源，Qdrant 是派生索引
- Qdrant 不可用时自动 fallback keyword search
- `sandbox/test_tool_handler_client.py` 是 ToolHandler 级调试，非真实 MCP stdio 客户端

## 文档索引

| 文档 | 说明 |
|------|------|
| `docs/source-deployment.md` | 源码部署空库流程 |
| `docs/部署指南.md` | 部署模式/端口/启动顺序 |
| `docs/ClaudeCode接入配置.md` | .mcp.json 配置示例 |
| `docs/ClaudeCode记忆工作流.md` | Claude Code 使用规范 |
| `docs/Agent使用规范.md` | Agent 调用原则 |
| `docs/Agent技能模板.md` | 可复制到其他项目的 CLAUDE.md 模板 |
| `docs/正式使用检查清单.md` | 启动前/每周/升级检查 |
| `docs/知识审核指南.md` | approve/reject/deprecate 标准 |
| `docs/deployment.md` | 部署指南（英文，已合并到部署指南.md） |

## 许可

MIT

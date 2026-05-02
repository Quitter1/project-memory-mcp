# Project Memory MCP

## 项目定位

MCP 服务，为 Claude Code、Codex、Cursor 等任务型 AI 提供**项目长期记忆能力**。

不是简单的向量数据库查询工具，而是**项目知识治理服务**。

### 核心功能

- **任务前**：检索项目相关知识，提供 context_pack
- **任务后**：沉淀候选知识，规则审核 + 人工确认
- **全周期**：管理知识生命周期，防止错误知识污染长期记忆
- **多项目**：支持多项目隔离 + 跨项目共享知识复用

## MVP 范围

### 已实现（阶段 0）

- [x] 项目脚手架与配置文件
- [x] 文档与开发规范

### 待实现

- [ ] 数据模型 + SQLite 持久化
- [ ] 多项目识别
- [ ] 项目隔离检索
- [ ] 候选知识提交 + 规则审核
- [ ] keyword search + context_pack 输出
- [ ] stdio MCP tools（9 个）
- [ ] audit log

### MVP 不包含

- Web UI
- 真实 LLM Reviewer（仅 rule-based reviewer）
- 完整 Qdrant 集成（仅 mock vector store）
- 多 collection 管理
- OAuth / 多用户权限
- 复杂导入导出

## 目录结构

```
project-memory-mcp/
├── CLAUDE.md              # 项目开发规则
├── README.md              # 项目说明（本文件）
├── pyproject.toml         # Python 项目配置
├── .gitignore
├── config/
│   ├── projects.yml       # 多项目配置（权威配置源）
│   ├── server.yml         # 服务级配置
│   └── memory-policy.yml  # 全局知识入库策略
├── data/                  # 运行时数据（Git 排除）
│   ├── memory.db          # SQLite 主库
│   └── backups/           # JSONL 备份（按项目分目录）
├── docs/
│   ├── architecture.md    # 架构文档
│   ├── memory-policy.md   # 知识入库策略文档
│   ├── mcp-tools.md       # MCP 工具接口文档
│   └── projects-config.md # 项目配置说明
├── src/project_memory_mcp/
│   ├── server.py          # MCP Server（FastMCP 风格）
│   ├── config/            # 配置加载模块
│   ├── models/            # 数据模型
│   ├── db/                # 数据库层（SQLite）
│   ├── vector/            # 向量存储（mock + Qdrant 预留）
│   ├── embedding/         # Embedding（mock + 预留）
│   ├── knowledge/         # 知识治理（审核、去重、校验）
│   ├── project/           # 项目识别与管理
│   ├── retrieval/         # 检索模块（keyword + semantic）
│   ├── tools/             # MCP 工具实现
│   └── utils/             # 工具函数
├── tests/                 # 测试
├── scripts/               # 脚本
└── sandbox/               # 开发调试
```

## 后续阶段计划

| 阶段 | 内容 | 预计 |
|------|------|------|
| 0 | 项目脚手架与配置文件 | 当前 |
| 1 | 数据模型 + SQLite 持久化 | 下一阶段 |
| 2 | 配置加载 + 项目识别 | - |
| 3 | 检索模块（keyword-first） | - |
| 4 | 知识治理（多因素审批 + 敏感信息检测） | - |
| 5 | MCP 工具实现（9 个 MVP tools） | - |
| 6 | 多项目集成测试 + 演示数据 | - |

## 本地初始化

```bash
# 1. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

# 2. 安装依赖
pip install -e ".[dev]"

# 3. 初始化数据库
python scripts/init_db.py

# 4. 同步项目配置
python scripts/sync_projects.py

# 5. 填充演示数据（可选）
python scripts/seed_demo_data.py

# 6. 运行测试
pytest tests/ -v
```

## MVP MCP 工具（9 个）

| 工具 | 分类 |
|------|------|
| `list_projects` | 项目识别 |
| `resolve_project` | 项目识别 |
| `get_project_profile` | 项目识别 |
| `search_project_context` | 知识检索 |
| `propose_memory` | 知识写入 |
| `list_memories` | 知识查询 |
| `approve_memory` | 知识治理 |
| `reject_memory` | 知识治理 |
| `deprecate_memory` | 知识治理 |

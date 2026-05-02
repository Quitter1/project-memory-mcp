# 架构文档 — project-memory-mcp

## 整体架构

```
┌─────────────────────────────────────────────────────┐
│                   MCP Client（Claude Code / Codex）   │
│                       stdio JSON-RPC                 │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                 MCP Server（FastMCP）                  │
│  server.py: 工具注册 + 参数校验 + 业务分发             │
└─────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│  项目识别器       │ │  检索模块     │ │  知识治理        │
│  resolver.py    │ │  search.py   │ │  governance.py  │
│  多策略项目匹配   │ │  keyword+     │ │  多因素审批      │
│                 │ │  semantic     │ │  敏感信息检测    │
└─────────────────┘ └─────────────┘ └─────────────────┘
          │               │               │
          └───────────────┼───────────────┘
                          ▼
┌─────────────────────────────────────────────────────┐
│                   数据访问层 (db/)                     │
│  memory_repo.py  │  project_repo.py  │  audit_repo.py │
└─────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│  SQLite 主库     │ │ Vector Store │ │  JSONL 备份     │
│  memory.db      │ │ (Mock/Qdrant)│ │  (按项目分目录)  │
└─────────────────┘ └─────────────┘ └─────────────────┘
```

## 分层职责

### server 层
- `server.py`：MCP FastMCP 实例创建、工具注册、启动
- 不包含业务逻辑，只做类型转换和异常处理

### tools 层
- `tools/handlers.py`：工具路由，根据 tool name 分发到对应处理函数
- 每个工具一个文件，包含参数 schema 和业务逻辑调用
- `tools/` 下文件调用 `project/`、`retrieval/`、`knowledge/` 的服务

### project 层
- `resolver.py`：多策略项目识别（workspace_path、files、description）
- `manager.py`：项目 CRUD + sync_projects（YAML → SQLite）
- `profile.py`：项目画像构建（统计信息聚合）

### retrieval 层
- `search.py`：统一搜索入口，三级范围检索
- `keyword_search.py`：SQLite LIKE/FTS keyword search（保底）
- `filter_builder.py`：过滤条件构建（scope、status、project_id）
- `ranker.py`：结果排序 + context_pack 组装

### knowledge 层
- `governance.py`：治理核心，多因素审批判定
- `validator.py`：内容安全校验（blocked + warning 两级检测）
- `deduplicator.py`：哈希去重 + 语义相似检测
- `lifecycle.py`：双状态机（status + index_status）
- `reviewer.py`：rule-based reviewer + LLM reviewer 接口预留

### db 层
- `connection.py`：SQLite 连接（WAL 模式、foreign_keys = ON）
- `migrations.py`：版本化 schema 迁移
- `memory_repo.py`：memory_items + memory_tags + memory_relations CRUD
- `project_repo.py`：projects CRUD
- `audit_repo.py`：audit_log 写入

### config 层
- `loader.py`：YAML 加载 + 校验 + sync_projects()
- `schema.py`：配置 dataclass 定义

### vector 层
- `base.py`：VectorStore 抽象接口
- `mock_store.py`：numpy 内存计算（MVP）

### embedding 层
- `base.py`：Embedder 抽象接口
- `mock_embedder.py`：确定性伪向量（MVP）

## 数据流

### 检索流程

```
search_project_context(query, project_id?)
       │
       ▼
  resolver.resolve()  ─── 确定 project_id
       │
       ▼
  search.py
       │
       ├──► keyword_search.py  ─── SQLite LIKE/FTS    ──┐
       │                                                 │
       └──► vector_store.search() (best-effort)  ────────┤
                                                         │
                                                         ▼
                                                  ranker.merge()
                                                         │
                                                         ▼
                                                  context_pack 输出
```

### 入库流程

```
propose_memory(title, content, project_id?, ...)
       │
       ▼
  resolver.resolve()  ─── 确定 project_id
       │
       ▼
  validator.validate(content)
       │
       ├── blocked 命中 ──► 拒绝，只写 audit_log
       │
       └── 通过
              │
              ▼
         deduplicator.check(content_hash)
              │
              ▼
         governance.determine_status()
              │  (多因素判定：confidence + scope + source_type
              │   + risk_level + review_policy + conflict)
              │
              ├──► approved ──► 写入 SQLite + (可选)向量化
              │
              └──► pending_review ──► 写入 SQLite，等待审批
```

## 关键设计决策

1. **keyword-first**：keyword search 永远可用，vector search 失败不影响主流程
2. **双状态**：status 管治理，index_status 管向量化，互不阻塞
3. **YAML 是权威配置源**：projects.yml 驱动项目识别和策略，SQLite 是运行时缓存
4. **blocked > high > normal**：敏感信息三级处理，严重违规不保存原文
5. **多因素审批**：单一 confidence 阈值不足以判断是否自动批准

## 当前实现状态

- [x] 阶段 0：项目脚手架与配置文件
- [ ] 阶段 1：数据模型 + SQLite 持久化
- [ ] 阶段 2：配置加载 + 项目识别
- [ ] 阶段 3：检索模块
- [ ] 阶段 4：知识治理
- [ ] 阶段 5：MCP 工具实现
- [ ] 阶段 6：多项目集成测试

## 相关文档

- [memory-policy.md](memory-policy.md) — 知识入库策略
- [mcp-tools.md](mcp-tools.md) — MCP 工具接口
- [projects-config.md](projects-config.md) — 项目配置说明

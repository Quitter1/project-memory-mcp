# 阶段 0 完成报告

## 完成时间

2026-05-02

## 阶段 0.5 收尾检查（2026-05-02）

### 修改的文件
- `.gitignore` — 新增 `qdrant/` 排除规则
- `config/server.yml` — Qdrant 配置改为详细格式（host/http_port/grpc_port/executable_path/storage_path/collection），enabled: false

### 删除的文件
- `__pycache__/` × 4 个目录（knowledge/models/utils/根级）— 已全部清理
- `*.pyc` × 16 个文件 — 已全部清理

### 自检确认
| 检查项 | 状态 |
|--------|------|
| `__pycache__` 和 `*.pyc` 全部清理 | ✅ |
| `.gitignore` 包含 `__pycache__/`, `*.py[cod]`, `.venv/`, `.env`, `data/`, `qdrant/` | ✅ |
| `config/server.yml` Qdrant 配置详细，`enabled: false` | ✅ |
| MVP 工具统一 9 个（README/docs/mcp-tools/docs/memory-policy 一致） | ✅ |
| `reject_memory` 只拒绝 candidate/pending_review | ✅ |
| `deprecate_memory` 只废弃 approved | ✅ |
| SQLite 是主存储（README/CLAUDE/docs/architecture 均有说明） | ✅ |
| Qdrant 只是后续检索增强，不可用不影响主流程 | ✅ |
| keyword search 保底可用（docs/architecture:59, docs/mcp-tools:218） | ✅ |
| 无真实 Qdrant 集成代码 | ✅ |

### 进入 Phase 1 条件判定
✅ **满足**。项目骨架干净、配置完整、文档一致，可以进入 Phase 1。 

## 创建文件清单

### 根目录配置 (4)
| 文件 | 用途 |
|------|------|
| `pyproject.toml` | Python 项目配置，依赖 mcp/pyyaml/pydantic/numpy |
| `.gitignore` | Git 排除规则（data/、__pycache__、.env、日志） |
| `README.md` | 项目说明：定位、MVP 范围、目录结构、9 个工具列表、初始化命令 |
| `CLAUDE.md` | 开发规则：约束条件、状态定义、禁止内容、开发流程 |

### config/ (3)
| 文件 | 用途 |
|------|------|
| `projects.yml` | 多项目权威配置源：4 个示例项目 + 1 个归档 + 全局默认值 + 共享规则 |
| `server.yml` | 服务级配置：数据库路径、Qdrant 连接、Embedding、Reviewer、备份 |
| `memory-policy.yml` | 全局策略：敏感信息检测规则（blocked/warning）、多因素审批条件、知识类型定义、标签分类 |

### docs/ (4)
| 文件 | 用途 |
|------|------|
| `architecture.md` | 架构文档：分层职责、数据流、设计决策、当前实现状态 |
| `memory-policy.md` | 知识策略：生命周期、双状态设计、自动批准 8 条件、敏感信息两级检测、去重规则、共享约束、治理工具职责边界 |
| `mcp-tools.md` | MCP 工具接口：9 个工具的完整参数定义、返回示例、错误格式、project_id 处理约定 |
| `projects-config.md` | 项目配置说明：字段详解、识别优先级、sync_projects 流程、添加新项目步骤 |

### src/project_memory_mcp/ (57 个文件)

#### models/ (5)
| 文件 | 用途 |
|------|------|
| `enums.py` | 8 个枚举：KnowledgeStatus(7 值)、IndexStatus(4 值)、ProjectStatus(3 值)、Scope(3 值)、RiskLevel(4 值)、SourceType(7 值)、KnowledgeType(14 值)、TagCategory(8 值)、RelationType(6 值) |
| `memory_item.py` | MemoryItem dataclass：30+ 字段含双状态、风险等级、来源证据、可见范围 |
| `project.py` | Project dataclass：含识别配置、知识策略、审核策略、yaml_hash |
| `search_result.py` | SearchResult + SearchResultSet dataclass |
| `context_pack.py` | ContextPack + ContextPackItem dataclass（三级分组输出格式） |

#### db/ (5)
| 文件 | 用途 |
|------|------|
| `connection.py` | SQLite 连接管理（WAL 模式骨架） |
| `migrations.py` | Schema 版本化迁移框架 |
| `memory_repo.py` | MemoryItem + tags + relations CRUD 骨架 |
| `project_repo.py` | Project CRUD + YAML 同步骨架 |
| `audit_repo.py` | 审计日志写入骨架 |

#### vector/ (2)
| 文件 | 用途 |
|------|------|
| `base.py` | VectorStore 抽象接口（upsert/search/delete/is_available） |
| `mock_store.py` | Mock 实现（numpy 内存计算，MVP 阶段不依赖 Qdrant） |

#### embedding/ (2)
| 文件 | 用途 |
|------|------|
| `base.py` | Embedder 抽象接口（embed_texts/embed_query/dimension） |
| `mock_embedder.py` | Mock 实现（确定性 SHA256 哈希伪向量） |

#### knowledge/ (5)
| 文件 | 用途 |
|------|------|
| `governance.py` | 治理核心骨架（多因素审批判定） |
| `validator.py` | 内容安全校验骨架（blocked + warning 两级检测） |
| `deduplicator.py` | 去重器骨架（哈希 + 语义） |
| `lifecycle.py` | 双状态机：VALID_TRANSITIONS 合法转换路由表已定义 |
| `reviewer.py` | RuleBasedReviewer 骨架 + LLMReviewer 预留接口 |

#### project/ (3)
| 文件 | 用途 |
|------|------|
| `resolver.py` | 多策略项目识别器：ResolveRequest/ResolveResult dataclass，6 级优先级 |
| `manager.py` | 项目管理骨架（sync_from_yaml/CRUD） |
| `profile.py` | 项目画像构建骨架 |

#### retrieval/ (4)
| 文件 | 用途 |
|------|------|
| `search.py` | 统一搜索入口骨架（keyword-first + 降级策略） |
| `keyword_search.py` | SQLite keyword search 骨架（永远可用的保底搜索） |
| `filter_builder.py` | 过滤条件构建骨架（SQL WHERE + Qdrant filter） |
| `ranker.py` | 结果排序/融合 + context_pack 组装骨架 |

#### tools/ (10)
| 文件 | 用途 |
|------|------|
| `handlers.py` | 工具路由 + 参数校验 + 业务分发骨架 |
| `list_projects.py` | list_projects 工具 |
| `resolve_project.py` | resolve_project 工具 |
| `get_project_profile.py` | get_project_profile 工具 |
| `search_context.py` | search_project_context 工具 |
| `propose_memory.py` | propose_memory 工具 |
| `list_memories.py` | list_memories 工具 |
| `approve_memory.py` | approve_memory 工具（审核通过候选知识） |
| `reject_memory.py` | reject_memory 工具（审核拒绝候选知识） |
| `deprecate_memory.py` | deprecate_memory 工具（废弃已生效知识） |

#### 其他模块 (6)
| 文件 | 用途 |
|------|------|
| `server.py` | MCP Server 入口骨架（FastMCP 风格，结构示例） |
| `__init__.py` | 包初始化（版本号） |
| `__main__.py` | python -m 入口 |
| `utils/logging.py` | 日志配置（stderr + 文件，stdout 不写日志） |
| `utils/hashing.py` | SHA256 内容哈希（已实现） |
| `utils/text.py` | 文本截断/清洗工具 |
| `backup/__init__.py` | 备份模块 |
| `backup/jsonl_backup.py` | JSONL 备份骨架 |
| `backup/markdown_backup.py` | Markdown 备份骨架 |

### tests/ (7)
| 文件 | 用途 |
|------|------|
| `conftest.py` | Pytest fixtures：临时数据库、sample_projects 示例数据（已实现） |
| `test_resolver.py` | 项目识别测试骨架（6 场景） |
| `test_memory_repo.py` | CRUD 测试骨架 |
| `test_search.py` | 检索隔离测试骨架（4 场景） |
| `test_governance.py` | 治理逻辑测试骨架（5 场景） |
| `test_validator.py` | 敏感信息检测测试骨架（5 场景） |
| `test_mcp_tools.py` | MCP 工具集成测试骨架 |
| `test_multi_project.py` | 多项目端到端测试骨架（4 场景） |

### scripts/ (3)
| 文件 | 用途 |
|------|------|
| `init_db.py` | 数据库初始化脚本骨架 |
| `sync_projects.py` | projects.yml → SQLite 同步脚本骨架 |
| `seed_demo_data.py` | 演示数据填充脚本骨架 |

### sandbox/ (1)
| 文件 | 用途 |
|------|------|
| `test_mcp_client.py` | 开发调试 MCP 客户端骨架 |

## 统计

- **总文件数**：57 个 src 文件 + 4 根目录配置 + 3 config + 4 docs + 7 tests + 3 scripts + 1 sandbox = 79 个常规文件
- **已实现逻辑**：`enums.py`（9 个枚举）、`lifecycle.py`（状态转换表）、`hashing.py`（SHA256 哈希）、`logging.py`（MCP 日志配置）、`conftest.py`（测试 fixtures）、`schema.py`（配置 dataclass）
- **骨架占位**：其余文件均为 TODO 标记

## 阶段 1 执行计划

### 目标：数据模型 + SQLite 持久化

### 实现清单

1. **db/migrations.py** — 实现 v1 schema 迁移
   - 创建 projects / memory_items / memory_tags / memory_relations / audit_log 五张表
   - 创建所有索引（10+ 个索引）
   - 实现 schema_version 版本追踪

2. **db/connection.py** — 实现 SQLite 连接管理
   - 连接时自动开启 WAL 模式 + foreign_keys = ON
   - 自动调用 run_migrations()
   - 上下文管理器支持

3. **db/memory_repo.py** — 实现 MemoryItem CRUD
   - create(item) / get_by_id(id) / update(id, fields) / delete(id)
   - find_by_hash(content_hash, project_id)
   - search_by_keyword(project_id, query, filters)
   - add_tag / remove_tag / get_tags
   - add_relation / remove_relation / get_relations

4. **db/project_repo.py** — 实现 Project CRUD
   - get_by_id / list_active / list_all
   - upsert(from_yaml_dict) / update_status
   - update_yaml_hash / check_yaml_consistency

5. **db/audit_repo.py** — 实现审计日志写入
   - log_action() 单条写入
   - batch_log() 批量写入

6. **scripts/init_db.py** — 完成数据库初始化脚本

7. **tests/test_memory_repo.py** — 完成 CRUD 单元测试

### 验证标准

```bash
pip install -e ".[dev]"
python scripts/init_db.py
pytest tests/test_memory_repo.py -v  # 全部通过
sqlite3 data/memory.db ".schema"     # 验证表结构正确
```

### 不实现的内容

- 不接 Qdrant
- 不接 LLM Reviewer
- 不实现 MCP tools
- 不实现 vector store 逻辑
- 不实现项目识别逻辑（memory_repo 是纯数据层）

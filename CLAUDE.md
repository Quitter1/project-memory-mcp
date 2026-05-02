# 执行前必读规则

每次开始新阶段或继续任务前，必须先阅读本文件，并在回复中用 5 条以内总结本次任务必须遵守的规则。

## 阶段结束硬性要求

每个阶段完成后必须：

1. 运行本阶段要求的 pytest。
2. 生成 progress/phase-{n}-summary.md。
3. 生成 progress/test-output-phase-{n}.txt。
4. 生成 progress/tree-phase-{n}.txt。
5. 生成 progress/git-status-phase-{n}.txt。
6. 生成 progress/git-diff-phase-{n}.patch。
7. 生成 review-pack-phase-{n}.zip。
8. 如果测试失败，不允许生成审阅包，也不允许进入下一阶段。
# Project Memory MCP 开发规则

## 项目定位

本项目是一个 MCP 服务，用于为 Claude Code、Codex、Cursor 等任务型 AI 提供项目长期记忆能力。

它不是简单的向量数据库查询工具，而是项目知识治理服务。

核心目标：

- 任务前检索项目知识
- 任务后沉淀候选知识
- 管理知识生命周期
- 防止错误知识污染长期记忆
- 支持项目级、模块级、表级、文件级上下文检索
- 支持多项目隔离和跨项目共享知识复用

## 开发语言

默认使用中文进行说明、注释和文档编写。

代码使用 Python 3.10+。

## MVP 技术栈

- Python 3.10+
- SQLite（元数据主存储，WAL 模式）
- MCP Python SDK（FastMCP 风格，不手写 JSON-RPC）
- Mock embedding / Mock vector store 先跑通流程
- PyYAML（配置文件解析）
- Qdrant（向量检索，预留接口，MVP 不接）

## 重要约束

### 数据/存储约束

1. **SQLite 是主存储**，Qdrant 只是检索增强（MVP 用 mock 替代）。
2. **projects.yml 是项目配置权威源**，SQLite project 表是运行时缓存，冲突时以 YAML 为准。
3. 所有知识必须有：id, project_id, module, type, title, content, content_hash, status, index_status, confidence, scope, source_type, risk_level, tags, created_at, updated_at。
4. 知识状态（status）和索引状态（index_status）必须解耦管理。

### 治理约束

1. **任务 AI 只能提交候选知识（candidate）**，不能绕过治理流程直接污染正式知识库。
2. **自动审批必须多因素联合判定**，不能只看 confidence。因素包括：scope、risk_level、source_type、安全校验、冲突检测、review_policy。
3. **shared/global 知识禁止自动批准**，必须进入 pending_review。
4. **严重敏感信息（私钥、真实 token、明文数据库密码）不保存原文**，仅写 audit_log，直接返回 blocked。
5. 疑似敏感信息标记 risk_level=high，强制 pending_review。

### 时间约定

1. 所有数据库时间字段使用 **UTC** 时区。
2. 对外输出统一 **ISO 8601** 格式：`YYYY-MM-DDTHH:MM:SSZ`。
3. Python 实现：`datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`。

### MCP 通信约束

1. **stdio MCP 服务不要向 stdout 写普通日志**，避免破坏 MCP JSON-RPC 通信。
2. 普通日志应写 stderr 或文件。
3. **MCP server 必须基于 MCP Python SDK / FastMCP 实现**，不要手写 JSON-RPC 协议层。
4. server.py 只做工具注册、参数校验和业务分发。

### 多项目隔离约束

1. 每条知识必须绑定 project_id。
2. 默认禁止跨项目检索，只有 scope=shared/global 的知识可跨项目复用。
3. 无法识别项目时返回 project_id_required 错误，必须提供 project_id/workspace_path/changed_files 之一。
4. 不同项目可拥有不同的识别规则、知识策略、审核策略。

## 知识状态

### status（治理状态）

- candidate：候选
- pending_review：待审核
- approved：已确认
- rejected：已拒绝
- deprecated：已废弃
- superseded：已被替代
- conflict：存在冲突

### index_status（索引状态）

- not_indexed：未写入向量库
- indexed：已写入向量库
- index_failed：向量化/写入失败
- stale：内容已更新但向量未更新

### source_type（来源类型）

- ai_inferred：AI 从代码/对话推断
- user_confirmed：用户明确确认
- code_verified：代码审查验证
- sql_verified：SQL 执行验证
- imported_doc：从文档导入
- manual_input：人工录入
- task_summary：任务总结沉淀

## 禁止入库内容

- 私钥、真实 token、明文数据库密码（blocked，不保存原文）
- API key 直接赋值
- 用户隐私
- 大段源码（连续 > 50 行）
- 大段 SQL dump（> 500 字符）
- 未验证的 AI 猜测
- 临时聊天废话
- 一次性日志

## 开发流程

### 开发前

1. 先阅读 README.md。
2. 再阅读 docs/architecture.md。
3. 涉及知识入库规则时阅读 docs/memory-policy.md。
4. 涉及 MCP 工具时阅读 docs/mcp-tools.md。
5. 不确定依赖和接口时先提出方案，不要硬猜。

### 开发后

1. 更新相关文档。
2. 补充测试。
3. 说明新增文件。
4. 说明当前完成度和下一步。

## 阶段计划

详见 docs/architecture.md 和项目 plan 文件。

当前阶段：阶段 4 — 知识治理（validator/deduplicator/lifecycle/reviewer/governance）。

### changed_files 路径规则

- changed_files 如果是绝对路径，可独立用于项目识别
- changed_files 如果是相对路径，必须同时提供 workspace_path 进行拼接
- 只有相对 changed_files 且无 workspace_path 时，resolver 不应误判项目
- Phase 5 MCP tools 实现时必须处理此规则

### 小数阶段编号约定

小数阶段使用整数编号保存文件：
- Phase 2.6 → phase-26-summary.md, review-pack-phase-26.zip
- Phase 2.7 → phase-27-summary.md, review-pack-phase-27.zip

### tag/relation 方法边界

- `add_tag` / `remove_tag` / `add_relation` / `remove_relation` 是 repo 内部低级方法
- **不允许 MCP tool 直接暴露**这些方法
- 如果未来需要暴露 tag/relation 管理工具，必须加 audit log 和事务包装



以后每个阶段完成后，请生成一个标准审阅包 review-pack.zip，方便交给外部 AI 审阅。

## 审阅包要求

文件名格式：

review-pack-phase-{阶段号}.zip

例如：

review-pack-phase-2.zip

## 必须包含

1. README.md
2. CLAUDE.md
3. pyproject.toml
4. config/
5. docs/
6. src/
7. tests/
8. scripts/
9. progress/
10. 本阶段测试输出文件：
   - progress/test-output-phase-{阶段号}.txt
11. 本阶段总结文件：
   - progress/phase-{阶段号}-summary.md
12. 项目文件树：
   - progress/tree-phase-{阶段号}.txt
13. git 状态：
   - progress/git-status-phase-{阶段号}.txt
14. git diff：
   - progress/git-diff-phase-{阶段号}.patch

## 必须排除

- .git/
- .venv/
- venv/
- __pycache__/
- *.pyc
- .pytest_cache/
- data/
- qdrant/
- *.db
- *.log
- .env
- node_modules/
- dist/
- build/

## 请新增脚本

新增 scripts/make_review_pack.py。

功能：

1. 自动生成 progress/tree-phase-{n}.txt
2. 自动生成 progress/git-status-phase-{n}.txt
3. 自动生成 progress/git-diff-phase-{n}.patch
4. 自动运行指定测试并保存到 progress/test-output-phase-{n}.txt
5. 自动打包 review-pack-phase-{n}.zip
6. 自动排除无关目录和缓存文件

示例命令：

python scripts/make_review_pack.py --phase 2 --test "pytest tests/test_config_loader.py tests/test_resolver.py -v"

完成后输出 zip 路径和包含文件数量。

## 审阅规则

每个阶段完成后，必须输出以下 5 项供外部审阅：

1. **review-pack zip** — 完整源码审阅包
2. **phase summary** — progress/phase-{n}-summary.md
3. **test-output** — progress/test-output-phase-{n}.txt
4. **git-status** — progress/git-status-phase-{n}.txt
5. **git-diff** — progress/git-diff-phase-{n}.patch

## 提交提醒

每个阶段通过审阅后，提醒用户做一次 Git commit：

```bash
git add .
git commit -m "phase 0-{n} {阶段名}"
```

例如：

```bash
git add .
git commit -m "phase 3.3 search limit fixes"
```

后续每个阶段单独 commit，例如：
- `phase 3.2 search edge-case fixes`
- `phase 3.3 search limit fixes`
- `phase 4 knowledge governance`

这样后续阶段的 `git diff` 才真正有价值。
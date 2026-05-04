# Agent 使用 project-memory-mcp 规范

## 每个任务开始前先查

Agent 在开始改代码/分析项目前，应优先调用：

- `resolve_project` — 识别当前项目
- `search_project_context` — 检索相关知识

查询时应提供：任务描述、相关文件路径、模块名、错误信息。

## 不能自动沉淀

默认禁止 Agent 自动调用 `propose_memory`。

只有满足以下条件才允许：

1. 用户明确要求"记录/沉淀/写入记忆"
2. 任务结束时用户让 Agent 总结候选知识
3. 明确标记为 `[CANDIDATE]`

## propose_memory 的内容要求

### 应该沉淀

- 项目长期约定
- 架构决策
- 反复出现的问题排查方法
- 已验证的代码模式
- 数据库表/字段含义
- 业务规则

### 不应该沉淀

- 临时日志
- 一次性报错
- 未验证猜测
- API Key/token/password
- 大段代码（>50 行）
- 大段 SQL（>500 字符）
- 用户隐私

## source_type 规范

| source_type | 含义 | 可信度 |
|-------------|------|--------|
| manual_input | 用户明确提供 | 高 |
| user_confirmed | 用户确认过 | 高 |
| code_verified | 代码中验证过 | 高 |
| imported_doc | 文档导入 | 中 |
| ai_inferred | AI 推断 | 中（默认不自动批准） |
| task_summary | 任务总结 | 低 |

## 审核流程

Agent 只能提交候选，最终由以下环节共同决定：

1. validator — 敏感信息检测
2. deduplicator — 去重
3. rule-based reviewer — 多因素审批
4. LLM Reviewer — 二次评审（可选）
5. 人工 review — 最终确认

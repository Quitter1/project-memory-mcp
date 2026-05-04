# Project Memory MCP 使用规则（Agent Skill 模板）

复制到其他项目的 CLAUDE.md 或 Agent skill 配置中。

## 任务开始

- 先调用 `resolve_project` 识别项目
- 再用 `search_project_context` 查询相关项目记忆
- 查询时提供 workspace_path、task_description、related_files

## 工作中

- 优先遵守项目记忆里的架构/业务/数据约定
- 如果记忆与代码冲突，以当前代码和用户确认优先
- 不要盲目相信低置信度记忆
- 不要自动调用 `propose_memory`

## 任务结束

- 只列出候选长期知识，不要自动写入
- 用户明确同意后才 `propose_memory`
- `propose_memory` 必须短、准、可复用
- 默认 `source_type=ai_inferred`，`confidence<=0.7`

## 禁止

- 禁止写入 API Key/token/password
- 禁止写入用户隐私
- 禁止写入大段日志
- 禁止写入未验证猜测
- 禁止为了通过审核而伪造 source_type
- 禁止绕过 governance 直接写入

## 示例提示词

任务开始：

```text
请通过 project-memory-mcp 搜索当前项目与 xxx 相关的记忆，只读取，不写入。
```

任务结束：

```text
请根据本次任务列出值得沉淀的候选知识，只列候选，不调用 propose_memory。
```

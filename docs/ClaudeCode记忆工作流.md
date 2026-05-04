# Claude Code 使用 project-memory-mcp 规范

## 核心原则

**AI 默认不允许自动 propose_memory。只有用户明确要求"沉淀/保存/记录为知识"时才允许。**

## 任务开始时

Claude Code 可以自动调用：

- `resolve_project` — 识别当前项目
- `search_project_context` — 检索相关知识
- `get_project_profile` — 了解项目统计

推荐提示词：

```text
开始任务前，请通过 project-memory-mcp 自动识别当前项目，
并搜索与本任务相关的项目知识。只读取，不写入。
```

## 任务执行中

- 根据 `search_project_context` 返回的知识辅助判断
- 引用已有项目约定
- **不允许自动 propose_memory**

## 任务结束后

只有用户明确说以下关键词时，才允许 `propose_memory`：

- "沉淀为项目知识"
- "记录到项目记忆"
- "保存这条经验"
- "记住这个"

### propose_memory 规范

1. 一次最多提交 1-3 条
2. title 必须具体，能描述知识内容
3. content 必须是长期有效的项目知识
4. source_type 默认 `ai_inferred`
5. confidence 默认不超过 0.7
6. **不允许包含**：密钥、token、密码、私钥、完整大段源码
7. 测试知识 title 必须以 `[CC_TEST]` 开头

## 推荐完整工作流

```text
search → 执行任务 → 用户确认 → propose → pending_review → 人工 approve/reject
```

## 禁止行为

- 用户未要求时自动 propose_memory
- 批量写入大量知识
- 包含敏感信息的知识
- 绕过 governance 直接修改数据库

# 知识审核指南

## 查看待审核知识

```bash
python scripts/review_memories.py list --status pending_review
```

## 审核标准

### 可 approve

- 明确、长期有效、项目特有
- 能帮助后续开发
- 不含敏感信息
- 不只是一次性任务过程
- 来源可信（user_confirmed / code_verified / sql_verified / manual_input）

### 应 reject

- 测试知识（`[CC_TEST]` 前缀）
- 描述模糊、无实质内容
- 很快过期的内容
- 和已有知识重复
- AI 猜测但没有代码/文档依据
- 包含大段源码（>50 行）或大段 SQL（>500 字符）

### 应 deprecate

- 以前正确，现在过期
- 项目结构已迁移
- 字段或接口已变更
- 被新知识取代

## 状态含义

| status | 含义 |
|--------|------|
| candidate | AI 提交的候选知识 |
| pending_review | 待人工审核 |
| approved | 审核通过，可被检索 |
| rejected | 审核拒绝（终态） |
| deprecated | 已废弃（终态） |
| superseded | 已被替代 |
| conflict | 存在冲突 |

## source_type 可信度

| source_type | 可信度 | 说明 |
|-------------|--------|------|
| user_confirmed | 高 | 用户明确确认 |
| code_verified | 高 | 代码审查验证 |
| sql_verified | 高 | SQL 执行验证 |
| manual_input | 高 | 人工录入 |
| ai_inferred | 中 | AI 推断 |
| imported_doc | 中 | 文档导入 |
| task_summary | 低 | 任务总结 |

## 清理测试知识

```bash
# 预览
python scripts/cleanup_test_memories.py --dry-run

# 执行清理
python scripts/cleanup_test_memories.py --reject --yes
```

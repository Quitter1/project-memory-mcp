# 知识入库策略文档 — project-memory-mcp

## 知识生命周期

```
AI 提交 candidate
       │
       ▼
  安全校验（validator）
       │
       ├── blocked ──► 直接拒绝（不保存原文）──► audit_log
       │
       └── 通过
              │
              ▼
         去重检测（deduplicator）
              │
              ├── 完全重复 ──► 拒绝（hash 匹配）
              │
              └── 通过
                     │
                     ▼
              多因素审批判定（governance）
                     │
                     ├── 自动批准 ──► approved ──► (可选)向量化 ──► indexed
                     │
                     └── 需审核 ──► pending_review
                                        │
                          ┌─────────────┴─────────────┐
                          ▼                           ▼
                     approve_memory            reject_memory
                          │                           │
                          ▼                           ▼
                      approved                    rejected
                          │
                ┌─────────┴─────────┐
                ▼                   ▼
          deprecate_memory    (长期有效)
                │
                ▼
           deprecated
```

## 状态说明

### 治理状态 (status)

| 状态 | 含义 | 进入方式 | 退出方式 |
|------|------|---------|---------|
| candidate | AI 提交的候选 | propose_memory | 校验通过 → pending_review |
| pending_review | 等待审核 | 不满足自动批准条件 | approve_memory / reject_memory |
| approved | 审核通过 | approve_memory / 自动批准 | deprecate / supersede |
| rejected | 审核拒绝 | reject_memory / blocked | 不可逆（可重新提交） |
| deprecated | 已废弃 | deprecate_memory | 不可逆 |
| superseded | 已被替代 | supersede_memory | 不可逆 |
| conflict | 存在冲突 | 冲突检测 | resolve → 回到原状态 |

### 索引状态 (index_status)

| 状态 | 含义 |
|------|------|
| not_indexed | 未写入向量库 |
| indexed | 已写入向量库 |
| index_failed | 向量化或写入失败 |
| stale | 内容更新后向量未同步 |

## 自动批准判定规则

以下条件**全部满足**时，知识自动批准：

1. `confidence >= project.auto_approve_threshold`
2. `scope == "project"`（shared/global 永不自动批准）
3. `risk_level in ("low", "medium")`（high/critical 永不自动批准）
4. 来源可信：
   - `source_type in ("user_confirmed", "code_verified", "sql_verified")`，或
   - `source_type == "ai_inferred" AND project.review_policy.allow_ai_auto_approve == True`
5. 安全校验通过（无敏感信息命中）
6. 无内容哈希冲突
7. 无语义冲突
8. `type` 不在 `project.review_policy.forbidden_auto_types` 中

## 敏感信息检测

### blocked 级别（不保存原文）

| 检测项 | 说明 |
|--------|------|
| 私钥 | SSH/TLS 私钥 (BEGIN PRIVATE KEY) |
| AWS AKIA | AWS IAM Access Key |
| 明文数据库密码 | `password=实际密码`（非 `${}` 占位符） |
| JDBC URL 含密码 | `jdbc:...password=实际密码` |

处理方式：
- **不保存** content 到 memory_items 表
- 写入 audit_log（标记 action=blocked）
- 返回 status=rejected, reason=blocked_sensitive

### warning 级别（risk_level=high，强制 pending_review）

| 检测项 | 说明 |
|--------|------|
| API Key 赋值 | `api_key = "xxx"` 模式 |
| Token 赋值 | `token = "xxx"` 模式 |
| 大段源码 | > 50 行连续代码 |
| 大段 SQL dump | > 500 字符 SQL |

处理方式：
- 内容正常保存
- risk_level 设为 high
- 强制进入 pending_review（不自动批准）

## 去重规则

### 哈希去重
- 计算 `content` 的 SHA256 哈希
- 同 project_id 下哈希相同 → 视为重复
- 返回错误 `duplicate_content_hash`

### 语义去重（best-effort）
- 使用向量相似度检测（vector store 可用时）
- 相似度 > 0.92 → 发出 warning（不影响入库）
- 提供已存在的相似知识列表

## 跨项目共享规则

### scope 定义

| scope | 含义 | 可见范围 |
|-------|------|---------|
| project | 项目私有 | 仅当前项目 |
| shared | 跨项目共享 | allowed_projects 中的项目 |
| global | 全局通用 | 所有项目 |

### 共享约束

1. shared/global 知识**永不自动批准**，必须人工审核
2. shared 知识**必须设置** `allowed_projects`
3. shared 知识最多允许 `sharing_rules.max_shared_projects` 个项目
4. 项目间存在冲突知识时，自动拒绝共享（`auto_deny_projects_on_conflict`）

## 禁止入库内容

见 CLAUDE.md 中"禁止入库内容"章节。

## 治理工具职责边界

| 工具 | 适用对象 | 操作 |
|------|---------|------|
| approve_memory | candidate / pending_review | status → approved |
| reject_memory | candidate / pending_review | status → rejected |
| deprecate_memory | approved / indexed | status → deprecated |

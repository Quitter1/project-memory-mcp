# 阶段 4.1 修复报告 — 治理层安全收口

## 完成时间

2026-05-02

## 修复类别

### 1. 强化敏感信息 blocked 规则 ✅

**validator.py 变更：**

- API Key / Token / Secret Key / Bearer Token 从 **warning 升级为 blocked**（不保存原文）
- 新增 6 个特定厂商 Key 检测规则：
  - `OPENAI_KEY_RE`: `sk-proj-` / `sk-svcacct-` 前缀
  - `ANTHROPIC_KEY_RE`: `sk-ant-` 前缀
  - `DEEPSEEK_KEY_RE`: `sk-` + 纯小写字母数字
  - `SECRET_ASSIGN_RE`: `secret` / `secret_key` / `private_key` 赋值
  - `BEARER_ASSIGN_RE`: `bearer` + token
  - `PWD_ASSIGN_RE`: `pwd = "..."` 明文密码
- `ValidationResult` 新增 `blocked_field` 字段，标明命中字段名
- BLOCKED_RULES 按优先级排序（特定厂商 Key 在泛化 API_KEY_ASSIGN_RE 之前）
- WARNING_RULES 仅保留大段源码/大段 SQL 检测（不参与正则匹配）

### 2. 全字段安全校验 ✅

**`ContentValidator.validate_persisted_payload()`：**

- 对 title, content, source_evidence 各字段, source_file, tags 逐字段检测
- 命中任一字段 → blocked，返回 `blocked_field` 指明具体字段
- 传播所有字段的 warnings 到最终结果中

**`KnowledgeGovernance.propose_memory()`：**

- 调用 `validate_persisted_payload()` 替代单字段 `validate()`
- blocked 审计日志仅保存安全摘要（title_present, content_length, blocked_reason, blocked_field 等）
- 绝对不保存原始敏感内容到 audit_log

### 3. 重复知识状态过滤 ✅

**`MemoryRepository.find_by_hash()`：**

- 新增 `active_statuses` 参数，支持按状态过滤
- SQL 使用 `status IN (...)` 动态条件

**`Deduplicator`：**

- 新增 `ACTIVE_STATUSES = {"candidate", "pending_review", "approved", "conflict"}`
- `check()` 和 `check_hash_only()` 传入 `active_statuses` 到 repo 查询
- rejected / deprecated / superseded 不再被视为强重复

### 4. duplicate_rejected 审计日志 ✅

**`KnowledgeGovernance.propose_memory()`：**

- 哈希重复时写 `audit_log(action="duplicate_rejected")`
- 审计日志仅保存安全摘要（title, content_length, type, duplicate_of, duplicate_title 等）
- 不保存完整原文

### 5. manual_input 可信来源 ✅

**`RuleBasedReviewer.TRUSTED_SOURCES`：**

- 新增 `SourceType.MANUAL_INPUT`
- 人工录入的知识享受与其他可信来源相同的自动批准资格

### 6. rejected 终态 ✅

**`LifecycleManager`：**

- `rejected → candidate` 转换已移除
- `TERMINAL_STATUSES` 新增 `KnowledgeStatus.REJECTED`
- `is_terminal("rejected")` 返回 True
- 再次 approve/reject 已 rejected 的知识抛出 GovernanceError

## 测试结果

```
206 passed in 2.50s
```

| 测试类 | 新增 | 说明 |
|--------|------|------|
| TestBlocked | +8 | OpenAI/Anthropic/DeepSeek/Secret/Bearer/Pwd blocked |
| TestWarning | -2 | API Key/Token 升级为 blocked（移至 TestBlocked） |
| TestPersistedPayload | +5 | 全字段校验 |
| TestLifecycle | +2 | rejected 终态验证 |
| TestReviewer | +3 | manual_input 可信来源 |
| TestGovernancePropose | +14 | 全字段校验/安全摘要/去重过滤/dup审计/manual_input |
| TestGovernanceApproveReject | +3 | rejected 终态集成验证 |

**新增测试总计：+35**（原 181 → 206）

## 修改文件

| 文件 | 变更 |
|------|------|
| `knowledge/validator.py` | blocked 规则从 4→11 条；新增 validate_persisted_payload()、blocked_field |
| `knowledge/lifecycle.py` | 移除 rejected→candidate；rejected 加入 TERMINAL_STATUSES |
| `knowledge/deduplicator.py` | 新增 ACTIVE_STATUSES；check/check_hash_only 过滤终态 |
| `knowledge/reviewer.py` | TRUSTED_SOURCES 新增 MANUAL_INPUT |
| `knowledge/governance.py` | 全字段校验、安全摘要、duplicate_rejected 审计 |
| `db/memory_repo.py` | find_by_hash() 新增 active_statuses 参数 |
| `tests/test_validator.py` | 16 blocked + 4 warning + 1 batch + 5 persisted_payload = 26 tests |
| `tests/test_governance.py` | 14 lifecycle + 14 reviewer + 15 propose + 14 approve/reject = 57 tests |
| `CLAUDE.md` | 更新当前阶段为 4.1 |

## 审阅包

`reviews/review-pack-phase-41.zip`

## 进入 Phase 5

✅ 可以。Phase 5 为 MCP 工具实现（8 个工具 + server.py + handlers）。

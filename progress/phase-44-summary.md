# 阶段 4.4 修复报告 — blocked_field 脱敏

## 完成时间

2026-05-03

## 修复

### 1. blocked_field 脱敏 — validator 层 ✅

**问题**：source_evidence dict key 命中敏感信息时，key 原文（如 `OPENAI_API_KEY=sk-xxx`）被写入 blocked_field 路径，通过返回值和 audit_log 泄露。

**修复**：
- `_walk_source_evidence()` key 路径改用 `_safe_key_path(prefix)` 统一返回 `prefix.$key`
- 不再包含原始 key 文本
- 示例：`source_evidence.$key`、`source_evidence.nested.$key`、`source_evidence.items[0].$key`

### 2. blocked audit_log 中的 blocked_field 安全化 ✅

**问题**：即使 validator 层修了，audit_log 仍可能收到含敏感信息的 blocked_field。

**修复**：新增 `sanitize_blocked_field()` 函数：
- 检测 `sk-`、`OPENAI_API_KEY`、`token=`、`password=`、`pwd=` 等敏感标记
- 命中时将包含敏感标记的路径段替换为 `$key`
- 无法安全保留时返回 `sensitive_field_redacted`
- blocked audit safe_summary 统一使用 sanitize 后的 blocked_field

### 3. 返回结果中的 blocked_field 也安全 ✅

`propose_memory()` 返回的 `validation.blocked_field` 同样经过 `sanitize_blocked_field()` 处理。

## 测试结果

```
246 passed in 3.05s
```

| 测试类 | 新增 | 说明 |
|--------|------|------|
| TestPersistedPayload | +3 | blocked_field 不含原始 key |
| TestGovernanceApproveReject | +3 | audit_log + 返回结果 blocked_field 安全 |

**新增测试总计：+6**（原 240 → 246）

## 修改文件

| 文件 | 变更 |
|------|------|
| `knowledge/validator.py` | _walk_source_evidence() 用 _safe_key_path() 替代原始 key |
| `knowledge/governance.py` | 新增 sanitize_blocked_field()；blocked audit + 返回值均调用 |
| `tests/test_validator.py` | +3 Phase 4.4 测试 |
| `tests/test_governance.py` | +3 Phase 4.4 测试 |
| `CLAUDE.md` | 更新当前阶段为 4.4 |

## 审阅包

`reviews/review-pack-phase-44.zip`

## 进入 Phase 5

✅ 可以。Phase 5 为 MCP 工具实现（8 个工具 + server.py + handlers）。

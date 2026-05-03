# 阶段 4.3 修复报告 — 治理层安全收口（第三轮）

## 完成时间

2026-05-03

## 修复类别

### 1. source_evidence key 扫描 ✅

**问题**：`_walk_source_evidence()` 只扫描 value，不扫描 dict key。key 中如 `"OPENAI_API_KEY=sk-xxx": "safe"` 不会被 blocked。

**修复**：
- `_walk_source_evidence()` 同时扫描 dict key（字符串类型）
- key 路径使用 `$` 前缀区分：`source_evidence.$apiKeyName`
- list 内 dict 的 key 同样扫描：`source_evidence.items[0].$keyName`
- `KEY_PATH_SEP = "$"` 类常量控制分隔符

### 2. blocked audit_log 不保存 raw source_evidence_keys ✅

**问题**：blocked audit safe_summary 中的 `source_evidence_keys: list(source_evidence.keys())` 可能泄露敏感 key。

**修复**：改为仅保存安全元信息：
- `"source_evidence_present": true`
- `"source_evidence_key_count": N`

不保存任何 raw key 名。

### 3. 增强裸 sk- key 检测 ✅

**问题**：裸 `sk-abcDEF1234567890abcDEF1234567890`（混合大小写）可能绕过特定厂商 key 检测和 API_KEY_ASSIGN_RE。

**修复**：新增 `BARE_SK_KEY_RE` 规则：
- 模式：`sk-[A-Za-z0-9_-]{20,}`
- 排在 DEEPSEEK_KEY_RE 之后、API_KEY_ASSIGN_RE 之前
- 专用厂商 key（OpenAI/Anthropic/DeepSeek）仍优先命中

### 4. tags 类型轻量校验 ✅

**问题**：非字符串 tag（如 `tags=["ok", 123]`）可绕过 validator 进入 SQLite。

**修复**：`propose_memory()` 入口处增加类型校验：
- `tags` 必须为 `list[str]`，否则抛出 `GovernanceError("tags 必须是字符串列表")`
- 这是调用方参数错误，非内容风险，直接拒绝

## 测试结果

```
240 passed in 2.96s
```

| 测试类 | 新增 | 说明 |
|--------|------|------|
| TestBlocked | +2 | 裸 sk- 混合大小写 |
| TestPersistedPayload | +3 | source_evidence key 扫描 |
| TestGovernancePropose | +5 | source_evidence key 审计 |
| TestGovernanceApproveReject | +2 | tags 类型校验 |

**新增测试总计：+12**（原 228 → 240）

## 修改文件

| 文件 | 变更 |
|------|------|
| `knowledge/validator.py` | _walk_source_evidence() 扫描 key；新增 BARE_SK_KEY_RE |
| `knowledge/governance.py` | blocked audit 去 raw key；tags 类型校验 |
| `tests/test_validator.py` | +5 测试 |
| `tests/test_governance.py` | +7 测试 |
| `CLAUDE.md` | 更新当前阶段为 4.3 |

## 审阅包

`reviews/review-pack-phase-43.zip`

## 进入 Phase 5

✅ 可以。Phase 5 为 MCP 工具实现（8 个工具 + server.py + handlers）。

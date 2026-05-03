# 阶段 4.2 修复报告 — 治理层安全收口（第二轮）

## 完成时间

2026-05-03

## 修复类别

### 1. 修复 auto_approve_threshold=-1 未禁用自动批准 ✅

**问题**：`threshold=-1` 时 `confidence < -1` 永远为 False，导致任何正常 confidence 都会继续通过。

**修复**：`reviewer.py` 在 confidence 比较之前增加 `threshold < 0` 的提前判断：
- `threshold < 0` → 直接返回 `auto_approved=False`，原因："auto_approve_threshold < 0，项目禁用自动批准"
- 即使 source_type=user_confirmed/manual_input 也不自动批准
- 只有 `threshold >= 0` 才继续判断 confidence

### 2. 修复无引号 password/pwd 未 blocked ✅

**问题**：原有正则只匹配 `password="..."` / `pwd="..."`，不匹配 `password=secret123` / `pwd: secret123`。

**修复**：`PLAINTEXT_PASSWORD_RE` 和 `PWD_ASSIGN_RE` 改用交替正则：
- 引号分支：`['"](?!\s*\$\{)[^'"]{N,}['"]` — 匹配 `"值"`
- 无引号分支：`(?!\$\{)[^\s'"&;]{N,}` — 匹配 `值`
- `${DB_PASSWORD}` / `"${DB_PASSWORD}"` 全部正确排除
- JDBC 规则排在 PLAINTEXT_PASSWORD 之前，避免 JDBC URL 被泛化 password 规则误匹配

### 3. 修复 blocked audit_log 泄露 ✅

**问题**：blocked 时的 safe_summary 仍包含 `source_file`、`source_line` 等原始字段值，如果敏感信息在 source_file 中（如 `api_key=sk-xxx`），会被写入 audit_log。

**修复**：blocked audit safe_summary 改为仅保存安全元信息：
```json
{
  "title_present": true,
  "content_length": 123,
  "source_file_present": true,
  "source_evidence_keys": [...],
  "tag_count": 2,
  "blocked_reason": "...",
  "blocked_field": "...",
  "type": "...",
  "module": "...",
  "source_type": "...",
  "scope": "..."
}
```
不再保存：title 原文、content 原文、source_file 原文、source_evidence 原文、tags 原文。

### 4. source_evidence 递归扫描 ✅

**问题**：只扫描 `excerpt`、`reasoning`、`file` 三个固定 key，不检查嵌套 dict/list 中的字符串。

**修复**：新增 `_walk_source_evidence()` 递归遍历方法：
- 递归遍历 dict 和 list 中所有字符串值
- 路径格式：`source_evidence.nested.raw`、`source_evidence.items[0].context`
- 命中后 blocked_field 返回准确路径

### 5. 清理 bash.exe.stackdump ✅

- `git rm -f bash.exe.stackdump`
- `.gitignore` 新增 `*.stackdump`

### 6. governance.py 自查 ✅

- `python -m py_compile` 验证：语法正确，无重复字段

## 测试结果

```
228 passed in 2.67s
```

| 测试类 | 新增 | 说明 |
|--------|------|------|
| TestBlocked | +8 | 无引号 password/pwd + 占位符排除 |
| TestPersistedPayload | +4 | 递归扫描 source_evidence |
| TestReviewer | +4 | auto_approve_threshold=-1 禁用逻辑 |
| TestGovernancePropose | +6 | 集成测试 + 安全摘要审计 |

**新增测试总计：+22**（原 206 → 228）

## 修改文件

| 文件 | 变更 |
|------|------|
| `knowledge/reviewer.py` | threshold < 0 提前返回 |
| `knowledge/validator.py` | 无引号 password/pwd 正则；JDBC 置前；_walk_source_evidence() 递归扫描 |
| `knowledge/governance.py` | blocked audit safe_summary 移除原始字段值 |
| `.gitignore` | 新增 *.stackdump |
| `tests/test_validator.py` | +12 测试（password/pwd + 递归扫描） |
| `tests/test_governance.py` | +10 测试（threshold=-1 + 安全摘要审计） |
| `CLAUDE.md` | 更新当前阶段为 4.2 |

## 审阅包

`reviews/review-pack-phase-42.zip`

## 进入 Phase 5

✅ 可以。Phase 5 为 MCP 工具实现（8 个工具 + server.py + handlers）。

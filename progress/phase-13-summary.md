# 阶段 13 — LLM Reviewer / 二次评审接入

## 完成时间

2026-05-04

## 新增模块

### llm/types.py
- `LLMReviewResult`：decision/confidence/risk_level/reasons/suggested_type/tags/issues/error

### llm/config.py
- `LLMReviewerConfig`：只读非敏感字段
- API Key 永远从 `PROJECT_MEMORY_LLM_API_KEY` 环境变量读取
- `from_server_config()` 支持 server.yml + env

### llm/client.py
- `LLMClient`：OpenAI-compatible chat completions
- 支持重试、超时
- 日志只记 prompt_len / model / attempt / exc_type

### llm/prompts.py
- 二次评审 prompt 构造，不含敏感原文

### llm/reviewer.py
- `LLMReviewer`：parse + validate LLM JSON 输出
- `_parse_llm_response()`：JSON parse 失败 → pending_review

### llm/__init__.py

## 集成

### governance.py
- LLM Reviewer 在 rule-based reviewer 之后调用
- 可降级 auto_approve → pending_review
- 可建议 reject
- 失败不影响主流程

### app_context.py
- 从 server.yml + env 初始化 LLMReviewer

### config/server.yml
- `llm_reviewer` 段：enabled=false 默认关闭，fail_mode=pending_review

## 新增脚本

| 脚本 | 说明 |
|------|------|
| `scripts/check_llm_reviewer.py` | 检查配置/环境变量/--dry-run |
| `scripts/diagnose.py --llm-summary` | 显示 enabled/provider/env_present |

## 安全要求

- API Key 仅从环境变量读取
- 不写入任何文件/日志/audit_log/review pack
- check/diagnose 脚本只显示 "present/missing"

## 测试结果

```
390 passed in 13.28s
```

## 新增文件

| 文件 | 说明 |
|------|------|
| `llm/__init__.py` | 模块初始化 |
| `llm/types.py` | 类型定义 |
| `llm/config.py` | 配置（不存 SK） |
| `llm/client.py` | LLM client |
| `llm/prompts.py` | Reviewer prompt |
| `llm/reviewer.py` | LLM Reviewer |
| `scripts/check_llm_reviewer.py` | 检查脚本 |

## 修改文件

| 文件 | 变更 |
|------|------|
| `knowledge/governance.py` | LLM reviewer 集成 + 联动 |
| `app_context.py` | LLM reviewer 初始化 |
| `config/server.yml` | llm_reviewer 配置段 |
| `scripts/diagnose.py` | --llm-summary |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-13.zip`

## 是否可以开始真实 DeepSeek SK 验证

用户需先设置环境变量：
```
PROJECT_MEMORY_LLM_API_KEY=<测试SK>
PROJECT_MEMORY_LLM_BASE_URL=https://api.deepseek.com/v1
PROJECT_MEMORY_LLM_MODEL=<模型名>
```

然后修改 `config/server.yml llm_reviewer.enabled=true`，再运行：
```
python scripts/check_llm_reviewer.py --dry-run
```

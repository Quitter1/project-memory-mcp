# 阶段 6.3 报告 — 脚本收口 + 日志诊断

## 完成时间

2026-05-03

## 修复

### A. 脚本收口

| # | 修复 | 说明 |
|---|------|------|
| 1 | `_paths.py` 单ENV同源 | 与 server.py 路径逻辑一致 |
| 2 | `seed_demo_data.py` 退出码 | 全部缺失 exit 1；`--allow-missing-projects` 跳过 |
| 3 | `run_demo_flow.py` 失败检测 | 10 个关键步骤逐一检查 ok，失败 exit 1 |
| 4 | `test_scripts.py` 完整配置 | 使用全 demo 项目配置 + 失败场景测试 |

### B. 日志与诊断能力

| # | 功能 | 说明 |
|---|------|------|
| 5 | `utils/logging.py` RotatingFileHandler | 主日志 5MBx5 + errors.log |
| 6 | `request_id` | 所有 9 个 tool 响应含 `req_xxxxxxxx` |
| 7 | MCP tool 调用日志 | tool_start/success/error，安全摘要不含敏感原文 |
| 8 | 搜索诊断日志 | total_found/returned + 三组 count |
| 9 | 治理决策日志 | risk_level/decision/status |
| 10 | `config/server.yml` logging 配置 | level/log_dir/file_enabled/stderr_enabled |
| 11 | `scripts/diagnose.py` | 文件/数据库/项目/日志状态检查 |
| 12 | CLAUDE.md 日志规则 | 脱敏/禁用print/request_id 硬性规则 |

## 测试结果

```
327 passed in 6.45s
```

| 测试文件 | 新增 | 说明 |
|----------|------|------|
| test_mcp_tools.py | +1 | request_id 测试 |
| test_scripts.py | +1 | 失败场景测试 |

**新增测试总计：+2**（原 325 → 327）

## 修改文件

| 文件 | 变更 |
|------|------|
| `scripts/_paths.py` | 单ENV同源逻辑 |
| `scripts/seed_demo_data.py` | sys导入 + --allow-missing-projects + 退出码 |
| `scripts/run_demo_flow.py` | 失败跟踪 + 退出码 |
| `scripts/diagnose.py` | 新增：运行诊断 |
| `utils/logging.py` | RotatingFileHandler + request_id |
| `tools/handlers.py` | request_id + _dispatch + 工具日志 + 搜索/治理诊断 |
| `config/server.yml` | logging 配置段 |
| `CLAUDE.md` | 日志脱敏/request_id 硬性规则 |
| `tests/test_mcp_tools.py` | request_id 测试 |
| `tests/test_scripts.py` | 完整配置 + 失败场景 |

## 审阅包

`reviews/review-pack-phase-63.zip`

## 进入 Phase 7

✅ 可以。Phase 7 可选：真实 Qdrant / LLM Reviewer。

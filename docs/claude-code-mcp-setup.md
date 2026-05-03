# Claude Code MCP 接入配置

## 接入前检查

```bash
# 推荐：临时库 + demo 数据，不污染当前 data/memory.db
python scripts/test_mcp_stdio_client.py --seed-demo

# 如果要用当前真实数据库验证（会写入测试知识，不推荐频繁使用）
python scripts/test_mcp_stdio_client.py --use-current-db

# 基础检查
python scripts/check_mcp_server.py
python scripts/dev_check.py
python scripts/diagnose.py
```

## 推荐配置

在 Claude Code 配置中添加：

```json
{
  "mcpServers": {
    "project-memory-mcp": {
      "command": "python",
      "args": ["-m", "project_memory_mcp"],
      "env": {
        "PROJECT_MEMORY_CONFIG_DIR": "F:/project/project-memory-mcp/config",
        "PROJECT_MEMORY_DB_PATH": "F:/project/project-memory-mcp/data/memory.db",
        "PROJECT_MEMORY_LOG_DIR": "F:/project/project-memory-mcp/logs",
        "PROJECT_MEMORY_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Windows 路径注意事项

1. 路径建议用正斜杠：`F:/project/...`
2. 不要把日志写 stdout（MCP stdio 占用）
3. `python` 要指向当前虚拟环境或系统 Python
4. 如果 Claude Code 找不到模块，使用虚拟环境 Python 绝对路径：

```json
{
  "command": "F:/project/project-memory-mcp/.venv/Scripts/python.exe",
  "args": ["-m", "project_memory_mcp"]
}
```

## 故障排查

| 问题 | 解决 |
|------|------|
| `ModuleNotFoundError: mcp` | `pip install mcp` |
| 找不到 `projects.yml` | 检查 `PROJECT_MEMORY_CONFIG_DIR` |
| 没有 `memory.db` | `python scripts/init_db.py && python scripts/sync_projects.py` |
| MCP 启动后"卡住" | 正常 — stdio server 在等待客户端请求 |
| Claude Code 看不到 tools | 检查 command/args/env，查看 `logs/errors.log` |
| `project_not_found` | 确保 `config/projects.yml` 包含对应项目 |

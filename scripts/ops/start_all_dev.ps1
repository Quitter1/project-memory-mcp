# 开发用启动辅助 — 输出建议的启动命令（不全自动）
param()

Write-Host "=== Project Memory MCP 开发启动辅助 ==="
Write-Host ""
Write-Host "推荐启动顺序:"
Write-Host "  1. 启动 Qdrant"
Write-Host "     qdrant\qdrant.exe"
Write-Host "  2. 启动 embedding_server"
Write-Host "     cd F:\project\embedding_server && .venv\Scripts\Activate.ps1 && python -m embedding_server.main --config config.example.yml"
Write-Host "  3. 运行健康检查"
Write-Host "     powershell -File scripts\ops\health_check.ps1"
Write-Host "  4. 清理旧 MCP 进程"
Write-Host "     powershell -File scripts\kill_mcp_processes.ps1 -Kill"
Write-Host "  5. 打开 Claude Code"
Write-Host ""
Write-Host "注意: 不要将 API Key 写入任何配置文件"

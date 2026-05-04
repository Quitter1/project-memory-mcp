# 安全列出/终止 project-memory-mcp 相关进程
# 默认只列表，加 -Kill 才杀进程

param([switch]$Kill)

$processes = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match "project_memory_mcp|project-memory-mcp|project_memory" } |
    Select-Object ProcessId, CommandLine

if (-not $processes) {
    Write-Host "没有找到 project-memory-mcp 相关进程"
    exit 0
}

Write-Host "找到 $($processes.Count) 个进程:"
foreach ($p in $processes) {
    Write-Host "  PID=$($p.ProcessId) $($p.CommandLine)"
}

if ($Kill) {
    foreach ($p in $processes) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "  已终止 PID=$($p.ProcessId)"
    }
    Write-Host "完成"
} else {
    Write-Host ""
    Write-Host "默认只列表。使用 -Kill 终止进程:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/kill_mcp_processes.ps1 -Kill"
}

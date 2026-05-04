# 停止 project-memory-mcp 相关进程
# 默认只列出，带 -Kill 才杀

param([switch]$Kill)

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$killScript = Join-Path $ProjectRoot "scripts\kill_mcp_processes.ps1"

if (Test-Path $killScript) {
    if ($Kill) {
        & powershell -ExecutionPolicy Bypass -File $killScript -Kill
    } else {
        & powershell -ExecutionPolicy Bypass -File $killScript
    }
} else {
    # Fallback: inline check
    $procs = Get-CimInstance Win32_Process |
        Where-Object { $_.CommandLine -match "project_memory_mcp|project-memory-mcp" } |
        Select-Object ProcessId, CommandLine

    if (-not $procs) {
        Write-Host "没有找到 project-memory-mcp 相关进程"
    } else {
        Write-Host "找到 $($procs.Count) 个进程:"
        foreach ($p in $procs) { Write-Host "  PID=$($p.ProcessId)" }
        if ($Kill) {
            foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
            Write-Host "已终止"
        } else {
            Write-Host "使用 -Kill 终止"
        }
    }
}

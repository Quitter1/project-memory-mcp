# 备份 memory.db + projects.yml + server.yml
param()

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $ProjectRoot "backups\$Timestamp"

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$items = @(
    "data\memory.db",
    "data\memory.db-wal",
    "data\memory.db-shm",
    "config\projects.yml",
    "config\server.yml"
)

foreach ($item in $items) {
    $src = Join-Path $ProjectRoot $item
    if (Test-Path $src) {
        Copy-Item $src $BackupDir -Force
        Write-Host "  backup: $item"
    }
}

Write-Host "备份完成: $BackupDir"
Write-Host "不包括: logs, reviews, .env, API Key"

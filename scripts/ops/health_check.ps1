# 健康检查 — 依次运行 check_embedding/check_qdrant/diagnose/eval_search
param()

$ErrorActionPreference = "Stop"
$exitCode = 0
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path "$ScriptDir\..\.."

Push-Location $ProjectRoot

$checks = @(
    @("check_embedding", "python scripts/check_embedding.py"),
    @("check_qdrant", "python scripts/check_qdrant.py --warmup"),
    @("diagnose", "python scripts/diagnose.py --vector-summary"),
    @("eval_search", "python scripts/eval_search.py --mode hybrid")
)

foreach ($check in $checks) {
    $name = $check[0]
    $cmd = $check[1]
    Write-Host ""
    Write-Host "--- $name ---"
    try {
        $result = Invoke-Expression $cmd 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[FAIL] $name exit=$LASTEXITCODE"
            $exitCode = 1
        } else {
            Write-Host "[OK] $name"
        }
    } catch {
        Write-Host "[FAIL] $name : $_"
        $exitCode = 1
    }
}

Pop-Location
Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "Health check: ALL OK"
} else {
    Write-Host "Health check: FAILURES DETECTED"
}
exit $exitCode

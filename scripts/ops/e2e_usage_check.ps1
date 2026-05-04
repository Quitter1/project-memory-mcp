# 端到端使用验收 — 确认 MCP 服务具备 Agent 使用条件
param()

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path "$ScriptDir\..\.."
Push-Location $ProjectRoot

$exitCode = 0

$steps = @(
    @("诊断_向量", "python scripts/diagnose.py --vector-summary"),
    @("诊断_审核", "python scripts/diagnose.py --review-summary"),
    @("嵌入检查", "python scripts/check_embedding.py"),
    @("Qdrant检查", "python scripts/check_qdrant.py --warmup"),
    @("评测_hybrid", "python scripts/eval_search.py --mode hybrid"),
    @("搜索demo", "python scripts/search_context_demo.py --project rpa-electron --query '商品图上传到页面' --repeat 3")
)

foreach ($step in $steps) {
    $name = $step[0]
    $cmd = $step[1]
    Write-Host "--- $name ---"
    Invoke-Expression $cmd 2>&1 | Select-Object -Last 3
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] $name"
        $exitCode = 1
    }
}

Pop-Location
Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "Project Memory MCP is ready for agent usage."
} else {
    Write-Host "Some checks failed. Review output above."
}
exit $exitCode

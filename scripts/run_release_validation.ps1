param(
    [ValidateSet("local", "staging")]
    [string]$Environment = "local",
    [switch]$IncludePerformance,
    [switch]$IncludeE2e
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$arguments = @("scripts/release_validation.py", "--environment", $Environment)
if ($IncludePerformance) {
    $arguments += "--include-performance"
}
if ($IncludeE2e) {
    $arguments += "--include-e2e"
}
uv run python @arguments
exit $LASTEXITCODE

# AEGIS verify gate (Windows). Final line is the verdict: "VERIFY: PASS" (exit 0)
# or "VERIFY: FAIL (<stages>)" (exit 1).
#
# Usage:
#   scripts\verify.ps1                     # full offline gate (lint, types, tests, contracts)
#   scripts\verify.ps1 -TestPath <path>    # scoped: run ONLY that test file (pytest or vitest)
#   scripts\verify.ps1 -Build              # also run production builds (pnpm build)
#   scripts\verify.ps1 -Integration        # also run tests/integration (needs postgres+redis+minio up)
param(
    [string]$TestPath = "",
    [switch]$Integration,
    [switch]$Build
)

$ErrorActionPreference = "Continue"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

# This repo requires Node 22 (engines) and pnpm; both live under PNPM_HOME on this
# machine (standalone pnpm + `pnpm env use --global 22.x`). Prepend it when the
# current shell resolves the wrong node or no pnpm (child shells inherit stale PATH).
$pnpmHome = if ($env:PNPM_HOME) { $env:PNPM_HOME } else { Join-Path $env:LOCALAPPDATA "pnpm" }
$pnpmBin = Join-Path $pnpmHome "bin"
if (Test-Path (Join-Path $pnpmBin "node.exe")) {
    $env:PATH = "$pnpmBin;$env:PATH"
} elseif (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    $shim = Join-Path $env:LOCALAPPDATA "corepack-bin"
    if (Test-Path (Join-Path $shim "pnpm.CMD")) { $env:PATH = "$env:PATH;$shim" }
}

$failedStages = @()

function Invoke-Stage {
    param([string]$Name, [string]$Exe, [string[]]$StageArgs)
    Write-Host "=== [$Name] $Exe $($StageArgs -join ' ')"
    if (-not (Get-Command $Exe -ErrorAction SilentlyContinue)) {
        Write-Host "--- [$Name] FAILED (command not found: $Exe)"
        $script:failedStages += $Name
        return
    }
    $global:LASTEXITCODE = 0
    try {
        & $Exe @StageArgs
        $code = $LASTEXITCODE
    } catch {
        Write-Host $_.Exception.Message
        $code = 1
    }
    if ($code -ne 0) {
        Write-Host "--- [$Name] FAILED (exit $code)"
        $script:failedStages += $Name
    } else {
        Write-Host "--- [$Name] ok"
    }
}

if ($TestPath -ne "") {
    # Scoped iteration mode: run only the named test file.
    if ($TestPath -match '\.(test|spec)\.(ts|tsx|js|jsx|mts)$') {
        Invoke-Stage "scoped-vitest" "pnpm" @("exec", "vitest", "run", $TestPath)
    } else {
        Invoke-Stage "scoped-pytest" "uv" @("run", "pytest", $TestPath, "-q")
    }
} else {
    Invoke-Stage "format" "pnpm" @("format:check")
    Invoke-Stage "eslint" "pnpm" @("lint")
    Invoke-Stage "tsc" "pnpm" @("typecheck")
    Invoke-Stage "vitest" "pnpm" @("test")
    Invoke-Stage "ruff" "uv" @("run", "ruff", "check", ".")
    Invoke-Stage "mypy" "pnpm" @("typecheck:py")
    Invoke-Stage "import-linter" "uv" @("run", "lint-imports")
    Invoke-Stage "pytest" "uv" @("run", "pytest", "-q", "--ignore=tests/integration")
    Invoke-Stage "contracts" "pnpm" @("check-contracts")
    if ($Build) {
        Invoke-Stage "build" "pnpm" @("build")
    }
    if ($Integration) {
        Invoke-Stage "pytest-integration" "uv" @("run", "pytest", "tests/integration", "-q")
    }
}

if ($failedStages.Count -gt 0) {
    Write-Host "VERIFY: FAIL ($($failedStages -join ', '))"
    exit 1
}
Write-Host "VERIFY: PASS"
exit 0

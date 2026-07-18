# AEGIS verify gate (Windows). Final line is the verdict: "VERIFY: PASS" (exit 0)
# or "VERIFY: FAIL (<stages>)" (exit 1).
#
# Usage:
#   scripts\verify.ps1                     # full offline gate (lint, types, tests, contracts)
#   scripts\verify.ps1 -TestPath <path>    # scoped: run ONLY that test file (pytest or vitest)
#   scripts\verify.ps1 -Build              # also run production builds (pnpm build)
#   scripts\verify.ps1 -Integration        # also run tests/integration (needs postgres+redis+minio up)
#   scripts\verify.ps1 -Deployment          # validate/build/smoke the local production-shaped stack
param(
    [string]$TestPath = "",
    [switch]$Integration,
    [switch]$Build,
    [switch]$Deployment
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

function Invoke-DeploymentReadiness {
    $productionEnv = ".env.production.example"
    $composeFiles = @("-f", "docker-compose.yml", "-f", "docker-compose.prod.yml")
    $projectName = "aegis-phase33-verify"
    $terraformImage = "hashicorp/terraform:1.9.8@sha256:18f9986038bbaf02cf49db9c09261c778161c51dcc7fb7e355ae8938459428cd"
    $terraformRoot = Join-Path $repoRoot "infra\terraform"
    $terraformMount = "$terraformRoot`:/workspace"

    $env:AEGIS_PROD_ENV_FILE = $productionEnv
    Invoke-Stage "compose-dev-config" "docker" @("compose", "-f", "docker-compose.yml", "config", "--quiet")
    $prodConfigArgs = @("compose", "--env-file", $productionEnv) + $composeFiles + @("config", "--quiet")
    Invoke-Stage "compose-prod-config" "docker" $prodConfigArgs
    $prodBuildArgs = @("compose", "--project-name", $projectName, "--env-file", $productionEnv) + $composeFiles + @("build", "api", "web", "worker", "simulator")
    Invoke-Stage "compose-prod-build" "docker" $prodBuildArgs

    Invoke-Stage "terraform-fmt" "docker" @("run", "--rm", "-v", $terraformMount, "-w", "/workspace", $terraformImage, "fmt", "-check", "-recursive")
    foreach ($environmentName in @("dev", "staging", "production")) {
        $terraformCommand = "terraform -chdir=environments/$environmentName init -backend=false -input=false && terraform -chdir=environments/$environmentName validate"
        Invoke-Stage "terraform-$environmentName" "docker" @("run", "--rm", "--entrypoint", "/bin/sh", "-v", $terraformMount, "-w", "/workspace", $terraformImage, "-c", $terraformCommand)
    }

    $prodUpArgs = @("compose", "--project-name", $projectName, "--env-file", $productionEnv) + $composeFiles + @("up", "-d", "--wait")
    Invoke-Stage "compose-prod-up" "docker" $prodUpArgs
    Invoke-Stage "deploy-smoke" "uv" @("run", "python", "scripts/deploy_smoke_test.py", "--environment", "local", "--env-file", $productionEnv)
    $prodDownArgs = @("compose", "--project-name", $projectName, "--env-file", $productionEnv) + $composeFiles + @("down", "--volumes", "--remove-orphans")
    Invoke-Stage "compose-prod-down" "docker" $prodDownArgs
    $env:AEGIS_PROD_ENV_FILE = $null
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
    if ($Deployment) {
        Invoke-DeploymentReadiness
    }
}

if ($failedStages.Count -gt 0) {
    Write-Host "VERIFY: FAIL ($($failedStages -join ', '))"
    exit 1
}
Write-Host "VERIFY: PASS"
exit 0

#Requires -Version 5.1
<#
.SYNOPSIS
    Windows PowerShell port of scripts/deploy.sh: release checks, then deploy.

.DESCRIPTION
    Usage:
      scripts\deploy.ps1 --check      Run release checks only (default).
      scripts\deploy.ps1 --push       Run checks, then push clean main to origin/main.
      scripts\deploy.ps1 --frontend   Run checks, then deploy the synced main revision to Vercel production.

    --push triggers the existing Render deployment workflow only after CI succeeds.
    Vercel is intentionally not Git-connected; --frontend asks for confirmation and
    needs VERCEL_TOKEN, VERCEL_ORG_ID and VERCEL_PROJECT_ID. When they are absent
    they are read (names only, never printed) from %USERPROFILE%\.gramshiksha\secrets.env.

    Windows differences from the bash original:
      * venv binaries live in .venv\Scripts\ and the interpreter is 'python', not 'python3'.
      * -Yes skips the interactive confirmation (for CI / non-interactive shells).

    $ErrorActionPreference is deliberately left at its default: with 'Stop', a native
    tool writing to stderr (git, npm) raises a misleading NativeCommandError. Every
    external step is checked explicitly through $LASTEXITCODE instead.

    Options:
      -Yes                  skip the confirmation prompt (also --yes).
      -EnvFile <path>       fallback source for missing VERCEL_* values
                            (default %USERPROFILE%\.gramshiksha\secrets.env).

    Arguments are parsed by hand, not through a param() block: PowerShell would
    otherwise read '--check' as an unknown parameter named '-check' and refuse to
    run before any of this executes. Both 'check' and '--check' spellings work.
#>

$Root        = Split-Path -Parent $PSScriptRoot
$BackendDir  = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'
$VenvDir     = Join-Path $Root '.venv'
$Python      = Join-Path $VenvDir 'Scripts\python.exe'
$Ruff        = Join-Path $VenvDir 'Scripts\ruff.exe'

$script:DeployTestDir = $null
$script:PrevEnv       = @{}

function Fail {
    param([string]$Message)
    throw $Message
}

function Show-Usage {
    @'
Usage:
  scripts\deploy.ps1 --check      Run release checks only (default).
  scripts\deploy.ps1 --push       Run checks, then push clean main to origin/main.
  scripts\deploy.ps1 --frontend   Run checks, then deploy the synced main revision to Vercel production.

--push triggers the existing Render deployment workflow only after CI succeeds.
Vercel is intentionally not Git-connected; --frontend requires VERCEL_TOKEN,
VERCEL_ORG_ID and VERCEL_PROJECT_ID (or a secrets.env holding them) and asks
for confirmation. Pass -Yes to skip the prompt.
'@ | Write-Host
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Fail "required command not found: $Name"
    }
}

function Require-CleanMain {
    $branch = [string](git branch --show-current)
    $branch = $branch.Trim()
    if ($branch -ne 'main') {
        $shown = if ($branch) { $branch } else { 'detached' }
        Fail "deployment requires branch main (current: $shown)"
    }
    if (git status --porcelain --untracked-files=all) {
        Fail 'deployment requires a clean working tree'
    }
    git fetch --quiet origin main
    if ($LASTEXITCODE -ne 0) { Fail 'could not fetch origin/main' }
}

function Confirm-Step {
    param([string]$Prompt)
    if ($Yes) {
        Write-Host "$Prompt [auto-yes]"
        return
    }
    if ([Console]::IsInputRedirected) {
        Fail 'interactive confirmation is required for deployment modes (or pass -Yes)'
    }
    $answer = Read-Host "$Prompt [y/N]"
    if ($answer -notmatch '^[Yy]([Ee][Ss])?$') {
        Fail 'cancelled; no deployment action was taken'
    }
}

function Import-VercelEnv {
    param([string]$Path)
    if ($env:VERCEL_TOKEN -and $env:VERCEL_ORG_ID -and $env:VERCEL_PROJECT_ID) { return }
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return }
    Get-Content -LiteralPath $Path | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$') {
            $key = $Matches[1]
            if ($key -like 'VERCEL_*') {
                $value = $Matches[2].Trim().Trim('"').Trim("'")
                [System.Environment]::SetEnvironmentVariable($key, $value, 'Process')
            }
        }
    }
    if ($env:VERCEL_TOKEN -and $env:VERCEL_ORG_ID -and $env:VERCEL_PROJECT_ID) {
        Write-Host "Loaded VERCEL_* from $Path (values not shown)."
    }
}

function Set-CheckedEnv {
    param([string]$Name, [string]$Value)
    $script:PrevEnv[$Name] = [System.Environment]::GetEnvironmentVariable($Name, 'Process')
    [System.Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
}

function Restore-CheckedEnv {
    foreach ($name in $script:PrevEnv.Keys) {
        [System.Environment]::SetEnvironmentVariable($name, $script:PrevEnv[$name], 'Process')
    }
    $script:PrevEnv = @{}
}

function Invoke-ReleaseChecks {
    Require-Command node
    Require-Command npm
    Require-Command git

    # Node >= 22.12 (done in PowerShell: passing 'split(".")' to node -e loses the
    # inner quotes to PowerShell's native-argument quoting).
    $nodeVersion = ([string](node --version)).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $nodeVersion) { Fail 'could not run node --version' }
    $nodeParts = $nodeVersion.TrimStart('v').Split('.')
    $nodeMajor = [int]$nodeParts[0]
    $nodeMinor = [int]$nodeParts[1]
    if ($nodeMajor -lt 22 -or ($nodeMajor -eq 22 -and $nodeMinor -lt 12)) {
        Fail "Node.js >=22.12 is required (found $nodeVersion)"
    }

    if (-not (Test-Path -LiteralPath $Python)) {
        Require-Command python
        Write-Host "Creating virtualenv at $VenvDir"
        python -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { Fail 'could not create .venv' }
    }

    Set-CheckedEnv 'PIP_DISABLE_PIP_VERSION_CHECK' '1'
    & $Python -m pip install -r (Join-Path $BackendDir 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { Fail 'pip install failed' }

    Write-Host "`n== Backend lint and license =="
    if (Test-Path -LiteralPath $Ruff) {
        & $Ruff check (Join-Path $BackendDir 'app') (Join-Path $BackendDir 'tests')
    }
    else {
        & $Python -m ruff check (Join-Path $BackendDir 'app') (Join-Path $BackendDir 'tests')
    }
    if ($LASTEXITCODE -ne 0) { Fail 'ruff check failed' }

    & $Python (Join-Path $Root 'scripts\check_license.py')
    if ($LASTEXITCODE -ne 0) { Fail 'license guard failed' }

    Write-Host "`n== Backend tests (isolated temporary SQLite database) =="
    $script:DeployTestDir = Join-Path $env:TEMP ('gramshiksha-deploy-check-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $script:DeployTestDir -Force | Out-Null
    $dbUrl = 'sqlite:///' + ($script:DeployTestDir -replace '\\', '/') + '/gramshiksha-test.db'
    Set-CheckedEnv 'DATABASE_URL' $dbUrl
    Set-CheckedEnv 'JWT_SECRET'   'deploy-check-only-secret-0123456789abcdef0123456789abcdef'
    Set-CheckedEnv 'SENTRY_DSN'   ''
    Write-Host "  DATABASE_URL = $dbUrl"
    Push-Location $Root
    try {
        & $Python -m pytest -q (Join-Path $BackendDir 'tests')
        if ($LASTEXITCODE -ne 0) { Fail 'backend tests failed' }
    }
    finally { Pop-Location }

    Write-Host "`n== Frontend tests, build, audit, and mobile acceptance =="
    Push-Location $FrontendDir
    try {
        & npm ci
        if ($LASTEXITCODE -ne 0) { Fail 'npm ci failed' }

        & npm audit --audit-level=high
        if ($LASTEXITCODE -ne 0) { Fail 'npm audit failed' }

        & npm test
        if ($LASTEXITCODE -ne 0) { Fail 'frontend tests failed' }

        & npm run build
        if ($LASTEXITCODE -ne 0) { Fail 'frontend build failed' }

        & npx playwright install chromium
        if ($LASTEXITCODE -ne 0) { Fail 'playwright install failed' }

        & npm run e2e:mobile
        if ($LASTEXITCODE -ne 0) { Fail 'mobile e2e failed' }
    }
    finally { Pop-Location }
}

# --- argument parsing (bash-compatible: check | --check | -check) -----------
$Yes     = $false
$EnvFile = Join-Path $env:USERPROFILE '.gramshiksha\secrets.env'
$Mode    = $null

$rawArgs = @($args)
for ($i = 0; $i -lt $rawArgs.Count; $i++) {
    $arg   = [string]$rawArgs[$i]
    $lower = $arg.ToLowerInvariant()

    if ($lower -in @('--yes', '-yes', '-y', '--y')) {
        $Yes = $true
    }
    elseif ($lower -in @('--env-file', '-env-file', '--envfile', '-envfile')) {
        if ($i + 1 -lt $rawArgs.Count) { $EnvFile = [string]$rawArgs[$i + 1]; $i++ }
    }
    elseif ($lower -match '^--?(check|push|frontend|help|h)$') {
        $Mode = $lower
    }
    elseif ($lower -notmatch '^-') {
        $Mode = $lower
    }
    else {
        Show-Usage
        [Console]::Error.WriteLine("deploy: unknown option: $arg")
        exit 1
    }
}
if (-not $Mode) { $Mode = '--check' }

$normalized = $Mode.Trim() -replace '^-+', ''
$normalized = $normalized.ToLowerInvariant()

if ($normalized -in @('help', 'h')) {
    Show-Usage
    exit 0
}
if ($normalized -notin @('check', 'push', 'frontend')) {
    Show-Usage
    [Console]::Error.WriteLine("deploy: unknown mode: $Mode")
    exit 1
}

$exitCode = 0
try {
    Require-Command git

    switch ($normalized) {
        'check' { }
        'push' {
            Require-CleanMain
            git merge-base --is-ancestor origin/main HEAD
            if ($LASTEXITCODE -ne 0) {
                Fail 'local main diverges from origin/main; reconcile before pushing'
            }
        }
        'frontend' {
            Require-CleanMain
            $head   = ([string](git rev-parse HEAD)).Trim()
            $remote = ([string](git rev-parse origin/main)).Trim()
            if ($head -ne $remote) {
                Fail 'frontend deployment requires local main to match origin/main'
            }
            Import-VercelEnv -Path $EnvFile
            if (-not ($env:VERCEL_TOKEN -and $env:VERCEL_ORG_ID -and $env:VERCEL_PROJECT_ID)) {
                Fail 'set VERCEL_TOKEN, VERCEL_ORG_ID and VERCEL_PROJECT_ID in the environment (or in the secrets file)'
            }
        }
    }

    Invoke-ReleaseChecks

    switch ($normalized) {
        'check' {
            Write-Host "`nAll release checks passed. No deployment was triggered."
        }
        'push' {
            Confirm-Step 'Push this verified main revision to origin/main? Render deploys only after CI passes.'
            git push origin main
            if ($LASTEXITCODE -ne 0) { Fail 'git push failed' }
        }
        'frontend' {
            Confirm-Step 'Deploy this verified, synced main revision to Vercel production?'
            Push-Location $FrontendDir
            try {
                & npx --yes vercel deploy --prod --yes --token $env:VERCEL_TOKEN
                if ($LASTEXITCODE -ne 0) { Fail 'vercel deploy failed' }
            }
            finally { Pop-Location }
        }
    }
}
catch {
    [Console]::Error.WriteLine('deploy: ' + $_.Exception.Message)
    $exitCode = 1
}
finally {
    if ($script:DeployTestDir -and (Test-Path -LiteralPath $script:DeployTestDir)) {
        Remove-Item -LiteralPath $script:DeployTestDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    Restore-CheckedEnv
}

exit $exitCode

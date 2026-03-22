param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("doctor", "quickread", "paths", "web-ui")]
    [string]$Action,
    [string]$Source,
    [string]$ProjectName,
    [string]$Format = "both",
    [string]$Sessdata,
    [switch]$NoSessdata,
    [string]$VividRoot
)

function Get-StateFilePath {
    $skillRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
    return Join-Path $skillRoot "state\repo_root.json"
}

function Resolve-ExistingPath {
    param([string]$PathValue)
    try {
        return (Resolve-Path -LiteralPath $PathValue -ErrorAction Stop).Path
    } catch {
        return $null
    }
}

function Test-VividRepoRoot {
    param([string]$Candidate)
    if (-not $Candidate) {
        return $false
    }
    $resolved = Resolve-ExistingPath $Candidate
    if (-not $resolved) {
        return $false
    }
    return Test-Path (Join-Path $resolved "scripts\vivid_tool.ps1")
}

function Save-RepoRootState {
    param(
        [string]$RepoRoot,
        [string]$Source
    )
    $stateFile = Get-StateFilePath
    $stateDir = Split-Path -Parent $stateFile
    New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
    $payload = @{
        repo_root      = $RepoRoot
        source         = $Source
        updated_at_utc = [DateTime]::UtcNow.ToString("o")
    }
    $payload | ConvertTo-Json | Set-Content -Path $stateFile -Encoding UTF8
}

function Get-CachedRepoRoot {
    $stateFile = Get-StateFilePath
    if (-not (Test-Path $stateFile)) {
        return $null
    }
    try {
        $payload = Get-Content -Path $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $cachedRoot = [string]$payload.repo_root
        if (Test-VividRepoRoot $cachedRoot) {
            return (Resolve-ExistingPath $cachedRoot)
        }
        Write-Host "Ignoring stale cached Vivid repository: $cachedRoot" -ForegroundColor Yellow
        return $null
    } catch {
        Write-Host "Ignoring unreadable repo root state file: $stateFile" -ForegroundColor Yellow
        return $null
    }
}

function Resolve-RepoRootOrExit {
    $stateFile = Get-StateFilePath
    if ($VividRoot) {
        if (-not (Test-VividRepoRoot $VividRoot)) {
            Write-Host "Error: invalid -VividRoot path: $VividRoot" -ForegroundColor Red
            Write-Host "State file: $stateFile" -ForegroundColor Yellow
            exit 1
        }
        $resolved = Resolve-ExistingPath $VividRoot
        Save-RepoRootState -RepoRoot $resolved -Source "argument"
        Write-Host "Using -VividRoot: $resolved" -ForegroundColor Green
        Write-Host "Cached repo root in: $stateFile" -ForegroundColor DarkGray
        return $resolved
    }

    if ($env:VIVID_REPO_ROOT) {
        if (-not (Test-VividRepoRoot $env:VIVID_REPO_ROOT)) {
            Write-Host "Error: invalid VIVID_REPO_ROOT: $env:VIVID_REPO_ROOT" -ForegroundColor Red
            Write-Host "State file: $stateFile" -ForegroundColor Yellow
            exit 1
        }
        $resolved = Resolve-ExistingPath $env:VIVID_REPO_ROOT
        Save-RepoRootState -RepoRoot $resolved -Source "environment"
        Write-Host "Using VIVID_REPO_ROOT: $resolved" -ForegroundColor Green
        Write-Host "Cached repo root in: $stateFile" -ForegroundColor DarkGray
        return $resolved
    }

    $cached = Get-CachedRepoRoot
    if ($cached) {
        Write-Host "Using cached Vivid repository: $cached" -ForegroundColor Green
        Write-Host "Cache file: $stateFile" -ForegroundColor DarkGray
        return $cached
    }

    $detectedRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
    if (Test-VividRepoRoot $detectedRoot) {
        $resolved = Resolve-ExistingPath $detectedRoot
        Save-RepoRootState -RepoRoot $resolved -Source "auto_detect"
        Write-Host "Detected Vivid repository: $resolved" -ForegroundColor Green
        Write-Host "Cached repo root in: $stateFile" -ForegroundColor DarkGray
        return $resolved
    }

    Write-Host "Error: could not locate the Vivid repository." -ForegroundColor Red
    Write-Host ""
    Write-Host "Provide the repository location in one of these ways:" -ForegroundColor Yellow
    Write-Host "  1. Reuse the cached state file: $stateFile" -ForegroundColor Cyan
    Write-Host "  2. Set VIVID_REPO_ROOT, for example: `$env:VIVID_REPO_ROOT = 'C:\path\to\vivid'" -ForegroundColor Cyan
    Write-Host "  3. Pass -VividRoot 'C:\path\to\vivid'" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "The skill auto-detects correctly when it is kept under skill/vivid-operator/ inside the Vivid repo." -ForegroundColor Yellow
    exit 1
}

$repoRoot = Resolve-RepoRootOrExit
$tool = Join-Path $repoRoot "scripts\vivid_tool.ps1"
if (-not (Test-Path $tool)) {
    Write-Host "Error: could not find the Vivid entrypoint: $tool" -ForegroundColor Red
    exit 1
}

$invokeArgs = @{
    Action = $Action
}
if ($Source) { $invokeArgs.Source = $Source }
if ($ProjectName) { $invokeArgs.ProjectName = $ProjectName }
if ($Format) { $invokeArgs.Format = $Format }
if ($Sessdata) { $invokeArgs.Sessdata = $Sessdata }
if ($NoSessdata) { $invokeArgs.NoSessdata = $true }

& $tool @invokeArgs
exit $LASTEXITCODE

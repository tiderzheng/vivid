param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("doctor", "quickread", "paths", "web-ui")]
    [string]$Action,
    [string]$Source,
    [string]$ProjectName,
    [string]$Format = "both",
    [string]$DataDir,
    [ValidateSet("tiny", "base", "small", "medium", "large")]
    [string]$Model,
    [ValidateSet("local", "cloud")]
    [string]$ExecutionMode,
    [ValidateSet("local_only", "cloud_only", "both")]
    [string]$ArtifactTarget,
    [string]$CloudProfile,
    [string]$CloudBaseUrl,
    [string]$Sessdata,
    [switch]$NoSessdata,
    [string]$VividRoot
)

function Get-StateFilePath {
    $skillRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
    return Join-Path $skillRoot "state\skill_state.json"
}

function Get-LegacyRepoStateFilePath {
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

function Read-StatePayload {
    $stateFile = Get-StateFilePath
    if (-not (Test-Path $stateFile)) {
        return @{}
    }
    try {
        $payload = Get-Content -Path $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $result = @{}
        if ($payload.repo_root) { $result.repo_root = [string]$payload.repo_root }
        if ($payload.default_whisper_model) { $result.default_whisper_model = [string]$payload.default_whisper_model }
        if ($payload.default_data_dir) { $result.default_data_dir = [string]$payload.default_data_dir }
        if ($payload.execution_mode) { $result.execution_mode = [string]$payload.execution_mode }
        if ($payload.artifact_target) { $result.artifact_target = [string]$payload.artifact_target }
        if ($payload.cloud_profile) { $result.cloud_profile = [string]$payload.cloud_profile }
        if ($payload.cloud_base_url) { $result.cloud_base_url = [string]$payload.cloud_base_url }
        if ($payload.source) { $result.source = [string]$payload.source }
        if ($payload.updated_at_utc) { $result.updated_at_utc = [string]$payload.updated_at_utc }
        return $result
    } catch {
        Write-Host "Ignoring unreadable skill state file: $stateFile" -ForegroundColor Yellow
        return @{}
    }
}

function Save-SkillState {
    param(
        [hashtable]$Updates
    )
    $stateFile = Get-StateFilePath
    $stateDir = Split-Path -Parent $stateFile
    New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
    $payload = Read-StatePayload
    foreach ($key in $Updates.Keys) {
        if ($null -ne $Updates[$key] -and "$($Updates[$key])".Trim() -ne "") {
            $payload[$key] = "$($Updates[$key])"
        }
    }
    $payload.updated_at_utc = [DateTime]::UtcNow.ToString("o")
    $payload | ConvertTo-Json | Set-Content -Path $stateFile -Encoding UTF8
}

function Get-CachedRepoRoot {
    $payload = Read-StatePayload
    $cachedRoot = [string]$payload.repo_root
    if ($cachedRoot) {
        if (Test-VividRepoRoot $cachedRoot) {
            return (Resolve-ExistingPath $cachedRoot)
        }
        Write-Host "Ignoring stale cached Vivid repository: $cachedRoot" -ForegroundColor Yellow
    }

    $legacyFile = Get-LegacyRepoStateFilePath
    if (Test-Path $legacyFile) {
        try {
            $legacyPayload = Get-Content -Path $legacyFile -Raw -Encoding UTF8 | ConvertFrom-Json
            $legacyRoot = [string]$legacyPayload.repo_root
            if (Test-VividRepoRoot $legacyRoot) {
                $resolved = Resolve-ExistingPath $legacyRoot
                Save-SkillState @{
                    repo_root = $resolved
                    source = "legacy_repo_state"
                }
                return $resolved
            }
            Write-Host "Ignoring stale legacy repo root state file: $legacyRoot" -ForegroundColor Yellow
        } catch {
            Write-Host "Ignoring unreadable legacy repo root state file: $legacyFile" -ForegroundColor Yellow
        }
    }
    return $null
}

function Get-StateValue {
    param([string]$Key)
    $payload = Read-StatePayload
    if ($payload.ContainsKey($Key)) {
        return [string]$payload[$Key]
    }
    return $null
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
        Save-SkillState @{
            repo_root = $resolved
            source = "argument"
        }
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
        Save-SkillState @{
            repo_root = $resolved
            source = "environment"
        }
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
        Save-SkillState @{
            repo_root = $resolved
            source = "auto_detect"
        }
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
    if ($Action -eq "quickread") {
    if (-not $ExecutionMode -and -not $env:VIVID_EXECUTION_MODE) {
        $cachedExecutionMode = Get-StateValue "execution_mode"
        if ($cachedExecutionMode) {
            $ExecutionMode = $cachedExecutionMode
        }
    }
    if (-not $ArtifactTarget -and -not $env:VIVID_ARTIFACT_TARGET) {
        $cachedArtifactTarget = Get-StateValue "artifact_target"
        if ($cachedArtifactTarget) {
            $ArtifactTarget = $cachedArtifactTarget
        }
    }
    if (-not $CloudProfile -and -not $env:VIVID_CLOUD_PROFILE) {
        $cachedCloudProfile = Get-StateValue "cloud_profile"
        if ($cachedCloudProfile) {
            $CloudProfile = $cachedCloudProfile
        }
    }
    if (-not $CloudBaseUrl -and -not $env:VIVID_CLOUD_BASE_URL) {
        $cachedCloudBaseUrl = Get-StateValue "cloud_base_url"
        if ($cachedCloudBaseUrl) {
            $CloudBaseUrl = $cachedCloudBaseUrl
        }
    }
    if (-not $DataDir -and -not $env:VIVID_DATA_DIR) {
        $cachedDataDir = Get-StateValue "default_data_dir"
        if ($cachedDataDir) {
            $DataDir = $cachedDataDir
        }
    }
    if (-not $Model -and -not $env:VIVID_DEFAULT_MODEL) {
        $cachedModel = Get-StateValue "default_whisper_model"
        if ($cachedModel) {
            $Model = $cachedModel
        }
    }
    if ($DataDir) {
        $resolvedDataDir = [System.IO.Path]::GetFullPath($DataDir)
        $invokeArgs.DataDir = $resolvedDataDir
        Save-SkillState @{ default_data_dir = $resolvedDataDir }
    }
    if ($Model) {
        $invokeArgs.Model = $Model
        Save-SkillState @{ default_whisper_model = $Model }
    }
    if ($ExecutionMode) {
        $invokeArgs.ExecutionMode = $ExecutionMode
        Save-SkillState @{ execution_mode = $ExecutionMode }
    }
    if ($ArtifactTarget) {
        $invokeArgs.ArtifactTarget = $ArtifactTarget
        Save-SkillState @{ artifact_target = $ArtifactTarget }
    }
    if ($CloudProfile) {
        $invokeArgs.CloudProfile = $CloudProfile
        Save-SkillState @{ cloud_profile = $CloudProfile }
    }
    if ($CloudBaseUrl) {
        $invokeArgs.CloudBaseUrl = $CloudBaseUrl
        Save-SkillState @{ cloud_base_url = $CloudBaseUrl }
    }
}
if ($Sessdata) { $invokeArgs.Sessdata = $Sessdata }
if ($NoSessdata) { $invokeArgs.NoSessdata = $true }

& $tool @invokeArgs
exit $LASTEXITCODE

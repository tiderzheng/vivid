param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot)
)

$venvPath = Join-Path $RepoRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$lockFile = Join-Path $venvPath ".creating_lock"
$requirementsPath = Join-Path $RepoRoot "requirements.txt"
$torchMode = ($env:VIVID_TORCH_MODE ?? "").Trim().ToLowerInvariant()

if (Test-Path $venvPython) {
    return $venvPython
}

New-Item -ItemType Directory -Path $venvPath -Force | Out-Null

if (Test-Path $lockFile) {
    Write-Host "Virtual environment is being created. Waiting..." -ForegroundColor Yellow
    $timeoutSeconds = 300
    $elapsedSeconds = 0
    while ((Test-Path $lockFile) -and ($elapsedSeconds -lt $timeoutSeconds)) {
        Start-Sleep -Seconds 1
        $elapsedSeconds++
    }

    if (Test-Path $venvPython) {
        return $venvPython
    }

    Write-Error "Timed out waiting for the virtual environment to finish creating."
    exit 1
}

New-Item -ItemType File -Path $lockFile -Force | Out-Null

function Test-NvidiaGpuPresent {
    $nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if (-not $nvidiaSmi) {
        return $false
    }
    try {
        & $nvidiaSmi.Source *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Show-TorchInstallChoiceAndExit {
    param(
        [string]$PythonPath,
        [string]$RequirementsPath
    )

    Write-Host ""
    Write-Host "Detected an NVIDIA GPU." -ForegroundColor Yellow
    Write-Host "The default 'pip install -r requirements.txt' path often installs CPU-only torch," -ForegroundColor Yellow
    Write-Host "which makes Whisper run on CPU instead of CUDA." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Choose one path and rerun:" -ForegroundColor Cyan
    Write-Host "  CPU path  :" -NoNewline -ForegroundColor Cyan
    Write-Host " `$env:VIVID_TORCH_MODE='cpu'" -ForegroundColor White
    Write-Host "  CUDA path :" -ForegroundColor Cyan
    Write-Host "    1. `"$PythonPath`" -m pip install torch --index-url https://download.pytorch.org/whl/cu128" -ForegroundColor White
    Write-Host "    2. `"$PythonPath`" -m pip install -r `"$RequirementsPath`"" -ForegroundColor White
    Write-Host ""
    Write-Error "Stopped before installing dependencies so you can choose CPU or CUDA torch intentionally."
    exit 1
}

try {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Error "Python 3.10+ is required."
        exit 1
    }

    & $pythonCmd.Source -m venv $venvPath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
        Write-Error "Failed to create the virtual environment."
        exit 1
    }

    Write-Host "Installing runtime dependencies..." -ForegroundColor Yellow
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to upgrade pip in the virtual environment."
        exit 1
    }

    # Stop here on NVIDIA systems unless the user explicitly accepts CPU torch.
    if ($torchMode -ne "cpu" -and (Test-NvidiaGpuPresent)) {
        Show-TorchInstallChoiceAndExit -PythonPath $venvPython -RequirementsPath $requirementsPath
    }

    & $venvPython -m pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install runtime dependencies."
        exit 1
    }
} finally {
    Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
}

return $venvPython

param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot)
)

$venvPath = Join-Path $RepoRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$lockFile = Join-Path $venvPath ".creating_lock"
$requirementsPath = Join-Path $RepoRoot "requirements.txt"

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

    & $venvPython -m pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install runtime dependencies."
        exit 1
    }
} finally {
    Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
}

return $venvPython

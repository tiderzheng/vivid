param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8765
)

$repoRoot = Split-Path -Parent $PSScriptRoot

# Ensure the runtime virtual environment exists.
$venvPython = & "$PSScriptRoot\ensure_venv.ps1" -RepoRoot $repoRoot
if (-not $venvPython) {
    Write-Error "Could not resolve the virtual environment Python executable."
    exit 1
}

Push-Location $repoRoot
try {
    $env:PYTHONUTF8 = "1"
    & $venvPython -m uvicorn app.web:app --host $Host --port $Port
} finally {
    Pop-Location
}

param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8765
)

$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    $env:PYTHONUTF8 = "1"
    python -c "from app.services.dependency_bootstrap import ensure_opencv_dependency; ensure_opencv_dependency(raise_on_failure=False)" | Out-Null
    python -m uvicorn app.web:app --host $Host --port $Port
} finally {
    Pop-Location
}

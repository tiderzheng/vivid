param(
    [switch]$Fix = $false,
    [switch]$AutoInstall = $false
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = & "$PSScriptRoot\ensure_venv.ps1" -RepoRoot $repoRoot
if (-not $venvPython) {
    Write-Error "Could not resolve the virtual environment Python executable."
    exit 1
}

function Invoke-DoctorJson {
    Push-Location $repoRoot
    try {
        $env:PYTHONUTF8 = "1"
        return & $venvPython -m app.control_cli doctor
    } finally {
        Pop-Location
    }
}

$doctorJson = Invoke-DoctorJson
$shouldFix = $Fix -or $AutoInstall

if ($shouldFix) {
    $parsedDoctor = $doctorJson | ConvertFrom-Json
    if (-not $parsedDoctor.ok) {
        & $venvPython -m pip install -r (Join-Path $repoRoot "requirements.txt")
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to reinstall runtime dependencies."
            exit 1
        }
        $doctorJson = Invoke-DoctorJson
    }
}

$payload = $doctorJson | ConvertFrom-Json
$rows = @(
    @{ Name = "python"; Available = [bool]$payload.checks.python.available; Required = [bool]$payload.checks.python.required; Hint = $payload.checks.python.install_hint }
    @{ Name = "ffmpeg"; Available = [bool]$payload.checks.ffmpeg.available; Required = [bool]$payload.checks.ffmpeg.required; Hint = $payload.checks.ffmpeg.install_hint }
    @{ Name = "node"; Available = [bool]$payload.checks.node.available; Required = [bool]$payload.checks.node.required; Hint = $payload.checks.node.install_hint }
    @{ Name = "requests"; Available = [bool]$payload.checks.requests.available; Required = [bool]$payload.checks.requests.required; Hint = $payload.checks.requests.install_hint }
    @{ Name = "yt-dlp"; Available = [bool]$payload.checks.yt_dlp_python.available; Required = [bool]$payload.checks.yt_dlp_python.required; Hint = $payload.checks.yt_dlp_python.install_hint }
    @{ Name = "openai-whisper"; Available = [bool]$payload.checks.whisper.available; Required = [bool]$payload.checks.whisper.required; Hint = $payload.checks.whisper.install_hint }
    @{ Name = "torch"; Available = [bool]$payload.checks.torch.available; Required = [bool]$payload.checks.torch.required; Hint = $payload.checks.torch.install_hint }
    @{ Name = "opencv-python"; Available = [bool]$payload.checks.opencv.available; Required = [bool]$payload.checks.opencv.required; Hint = $payload.checks.opencv.install_hint }
    @{ Name = "bilibili helper"; Available = [bool]$payload.checks.bili_helper.exists; Required = [bool]$payload.checks.bili_helper.required; Hint = $payload.checks.bili_helper.install_hint }
    @{ Name = "douyin helper"; Available = [bool]$payload.checks.douyin_helper.exists; Required = [bool]$payload.checks.douyin_helper.required; Hint = $payload.checks.douyin_helper.install_hint }
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "              Vivid Doctor              " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

foreach ($row in $rows) {
    if ($row.Available) {
        $status = "OK "
        $color = "Green"
    } elseif ($row.Required) {
        $status = "ERR"
        $color = "Red"
    } else {
        $status = "OPT"
        $color = "Yellow"
    }

    $label = if ($row.Required) { "[required]" } else { "[optional]" }
    Write-Host "$status $($row.Name) $label" -ForegroundColor $color
    if (-not $row.Available) {
        Write-Host "    hint: $($row.Hint)" -ForegroundColor DarkGray
    }
}

Write-Host ""
if ($payload.ok) {
    Write-Host "All required dependencies are ready." -ForegroundColor Green
} else {
    Write-Host "Some required dependencies are missing." -ForegroundColor Red
}
Write-Host ""

$payload | ConvertTo-Json -Depth 8

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

function Test-TorchAndTorchaudioCudaAvailable {
    try {
        $output = & $venvPython -c "import torch, torchaudio; print('1' if torch.cuda.is_available() else '0')" 2>$null
        return (($output | Out-String).Trim() -eq "1")
    } catch {
        return $false
    }
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
        if ((Test-NvidiaGpuPresent) -and -not (Test-TorchAndTorchaudioCudaAvailable) -and (($env:VIVID_TORCH_MODE ?? "").Trim().ToLowerInvariant() -ne "cpu")) {
            Write-Host "" -ForegroundColor Yellow
            Write-Host "Detected an NVIDIA GPU." -ForegroundColor Yellow
            Write-Host "doctor --fix would reinstall 'requirements.txt' and may pull CPU-only torch/torchaudio." -ForegroundColor Yellow
            Write-Host "If you want CPU intentionally, set `$env:VIVID_TORCH_MODE='cpu' and rerun." -ForegroundColor Yellow
            Write-Host "If you want CUDA, install CUDA torch and torchaudio first, then rerun doctor." -ForegroundColor Yellow
            exit 1
        }
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
    @{ Name = "faster-whisper"; Available = [bool]$payload.checks.faster_whisper.available; Required = [bool]$payload.checks.faster_whisper.required; Hint = $payload.checks.faster_whisper.install_hint }
    @{ Name = "ctranslate2"; Available = [bool]$payload.checks.ctranslate2.available; Required = [bool]$payload.checks.ctranslate2.required; Hint = $payload.checks.ctranslate2.install_hint }
    @{ Name = "funasr"; Available = [bool]$payload.checks.funasr.available; Required = [bool]$payload.checks.funasr.required; Hint = $payload.checks.funasr.install_hint }
    @{ Name = "modelscope"; Available = [bool]$payload.checks.modelscope.available; Required = [bool]$payload.checks.modelscope.required; Hint = $payload.checks.modelscope.install_hint }
    @{ Name = "torch"; Available = [bool]$payload.checks.torch.available; Required = [bool]$payload.checks.torch.required; Hint = $payload.checks.torch.install_hint }
    @{ Name = "torchaudio"; Available = [bool]$payload.checks.torchaudio.available; Required = [bool]$payload.checks.torchaudio.required; Hint = $payload.checks.torchaudio.install_hint }
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

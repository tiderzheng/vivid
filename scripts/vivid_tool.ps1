param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("doctor", "paths", "quickread", "web-ui", "vision-configs", "vision-prompts", "vision-select-config", "vision-upsert-config", "vision-upsert-prompt", "transcription-presets", "transcription-select-preset", "transcription-upsert-preset")]
    [string]$Action,
    [string]$Source,
    [string]$ProjectName,
    [string]$Format = "both",
    [string]$DataDir,
    [string]$Platform,
    [string]$Model,
    [ValidateSet("local", "cloud")]
    [string]$ExecutionMode = "local",
    [ValidateSet("local_only", "cloud_only", "both")]
    [string]$ArtifactTarget = "local_only",
    [string]$CloudProfile,
    [string]$CloudBaseUrl,
    [string]$Sessdata,
    [switch]$NoSessdata,
    [string]$FfmpegBin,
    [string]$WhisperRoot,
    [ValidateSet("auto", "smart", "prefer_ocr", "force_ocr")]
    [string]$AcquisitionMode,
    [switch]$PreferOcr,
    [switch]$ForceOcr,
    [ValidateSet("auto", "internal", "ears4_api")]
    [string]$TranscriptionBackend,
    [ValidateSet("auto", "internal", "eyes_api")]
    [string]$VisionBackend,
    [int]$TranscribeTimeout,
    [int]$OcrTimeout,
    [string]$VisionApiConfigId,
    [int]$VisionTimeout,
    [int]$VisionSampleMs,
    [int]$VisionMinDurationMs,
    [string]$UiHost = "127.0.0.1",
    [int]$Port = 8765,
    [string]$Id,
    [string]$Name,
    [string]$ApiBase,
    [string]$ApiPath = "/v1/chat/completions",
    [int]$Timeout = 30,
    [string]$Group = "default",
    [string]$Note,
    [string]$Prompt,
    [string]$SystemPrompt,
    [string]$ApiKeyEnv,
    [string]$Content,
    [string]$Device = "auto",
    [string]$Language = "zh",
    [string]$Task = "transcribe",
    [switch]$ExtractAudio,
    [switch]$NoExtractAudio,
    [switch]$NoKeepFiles
)

$repoRoot = Split-Path -Parent $PSScriptRoot

function Get-VenvPython {
    $resolvedPython = & "$PSScriptRoot\ensure_venv.ps1" -RepoRoot $repoRoot
    if (-not $resolvedPython) {
        Write-Error "Could not resolve the virtual environment Python executable."
        exit 1
    }
    return $resolvedPython
}

function Invoke-ControlCli {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $venvPython = Get-VenvPython
    Push-Location $repoRoot
    try {
        $env:PYTHONUTF8 = "1"
        & $venvPython @Arguments
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    } finally {
        Pop-Location
    }
}

if ($Action -eq "doctor") {
    & "$PSScriptRoot\doctor.ps1"
    exit $LASTEXITCODE
}

$cliArgs = @("-m", "app.control_cli", $Action)

switch ($Action) {
    "quickread" {
        if (-not $Source) {
            throw "Source is required for quickread."
        }

        $cliArgs += @("--source", $Source, "--format", $Format)
        if ($ProjectName) { $cliArgs += @("--project-name", $ProjectName) }
        if ($DataDir) { $cliArgs += @("--data-dir", $DataDir) }
        if ($Platform) { $cliArgs += @("--platform", $Platform) }
        if ($Model) { $cliArgs += @("--model", $Model) }
        if ($ExecutionMode) { $cliArgs += @("--execution-mode", $ExecutionMode) }
        if ($ArtifactTarget) { $cliArgs += @("--artifact-target", $ArtifactTarget) }
        if ($CloudProfile) { $cliArgs += @("--cloud-profile", $CloudProfile) }
        if ($CloudBaseUrl) { $cliArgs += @("--cloud-base-url", $CloudBaseUrl) }
        if ($Sessdata) { $cliArgs += @("--sessdata", $Sessdata) }
        if ($NoSessdata) { $cliArgs += "--no-sessdata" }
        if ($FfmpegBin) { $cliArgs += @("--ffmpeg-bin", $FfmpegBin) }
        if ($WhisperRoot) { $cliArgs += @("--whisper-root", $WhisperRoot) }
        if ($AcquisitionMode) { $cliArgs += @("--acquisition-mode", $AcquisitionMode) }
        if ($PreferOcr) { $cliArgs += "--prefer-ocr" }
        if ($ForceOcr) { $cliArgs += "--force-ocr" }
        if ($TranscriptionBackend) { $cliArgs += @("--transcription-backend", $TranscriptionBackend) }
        if ($VisionBackend) { $cliArgs += @("--vision-backend", $VisionBackend) }
        if ($TranscribeTimeout) { $cliArgs += @("--transcribe-timeout", "$TranscribeTimeout") }
        if ($OcrTimeout) { $cliArgs += @("--ocr-timeout", "$OcrTimeout") }
        if ($VisionApiConfigId) { $cliArgs += @("--vision-api-config-id", $VisionApiConfigId) }
        if ($VisionTimeout) { $cliArgs += @("--vision-timeout", "$VisionTimeout") }
        if ($VisionSampleMs) { $cliArgs += @("--vision-sample-ms", "$VisionSampleMs") }
        if ($VisionMinDurationMs) { $cliArgs += @("--vision-min-duration-ms", "$VisionMinDurationMs") }
        if ($NoKeepFiles) { $cliArgs += "--no-keep-files" }
    }
    "web-ui" {
        $cliArgs += @("--host", $UiHost, "--port", "$Port")
    }
    "vision-select-config" {
        if (-not $Id) {
            throw "Id is required for vision-select-config."
        }
        $cliArgs += @("--id", $Id)
    }
    "vision-upsert-config" {
        if (-not $Id -or -not $Name -or -not $ApiBase) {
            throw "Id, Name, and ApiBase are required for vision-upsert-config."
        }
        $cliArgs += @("--id", $Id, "--name", $Name, "--api-base", $ApiBase, "--api-path", $ApiPath, "--timeout", "$Timeout", "--group", $Group)
        if ($Model) { $cliArgs += @("--model", $Model) }
        if ($Note) { $cliArgs += @("--note", $Note) }
        if ($Prompt) { $cliArgs += @("--prompt", $Prompt) }
        if ($SystemPrompt) { $cliArgs += @("--system-prompt", $SystemPrompt) }
        if ($ApiKeyEnv) { $cliArgs += @("--api-key-env", $ApiKeyEnv) }
    }
    "vision-upsert-prompt" {
        if (-not $Id -or -not $Name -or -not $Content) {
            throw "Id, Name, and Content are required for vision-upsert-prompt."
        }
        $cliArgs += @("--id", $Id, "--name", $Name, "--content", $Content)
    }
    "transcription-select-preset" {
        if (-not $Id) {
            throw "Id is required for transcription-select-preset."
        }
        $cliArgs += @("--id", $Id)
    }
    "transcription-upsert-preset" {
        if (-not $Id -or -not $Name) {
            throw "Id and Name are required for transcription-upsert-preset."
        }
        $cliArgs += @("--id", $Id, "--name", $Name, "--model", $Model, "--device", $Device, "--language", $Language, "--task", $Task)
        if ($ExtractAudio) { $cliArgs += "--extract-audio" }
        if ($NoExtractAudio) { $cliArgs += "--no-extract-audio" }
        if ($Note) { $cliArgs += @("--note", $Note) }
    }
}

Invoke-ControlCli -Arguments $cliArgs

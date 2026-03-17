param(
    [Parameter(Mandatory = $true)]
    [string]$Source,
    [string]$ProjectName,
    [string]$Format = "both",
    [string]$DataDir,
    [string]$Platform,
    [string]$Model,
    [string]$FfmpegBin,
    [string]$WhisperRoot,
    [ValidateSet("auto", "prefer_ocr", "force_ocr")]
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
    [switch]$NoKeepFiles,
    [switch]$JsonOutput
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$args = @("-m", "app.cli", $Source, "--format", $Format)

if ($ProjectName) {
    $args += @("--project-name", $ProjectName)
}
if ($DataDir) {
    $args += @("--data-dir", $DataDir)
}
if ($Platform) {
    $args += @("--platform", $Platform)
}
if ($Model) {
    $args += @("--model", $Model)
}
if ($FfmpegBin) {
    $args += @("--ffmpeg-bin", $FfmpegBin)
}
if ($WhisperRoot) {
    $args += @("--whisper-root", $WhisperRoot)
}
if ($AcquisitionMode) {
    $args += @("--acquisition-mode", $AcquisitionMode)
}
if ($PreferOcr) {
    $args += "--prefer-ocr"
}
if ($ForceOcr) {
    $args += "--force-ocr"
}
if ($TranscriptionBackend) {
    $args += @("--transcription-backend", $TranscriptionBackend)
}
if ($VisionBackend) {
    $args += @("--vision-backend", $VisionBackend)
}
if ($TranscribeTimeout) {
    $args += @("--transcribe-timeout", $TranscribeTimeout)
}
if ($OcrTimeout) {
    $args += @("--ocr-timeout", $OcrTimeout)
}
if ($VisionApiConfigId) {
    $args += @("--vision-api-config-id", $VisionApiConfigId)
}
if ($VisionTimeout) {
    $args += @("--vision-timeout", $VisionTimeout)
}
if ($VisionSampleMs) {
    $args += @("--vision-sample-ms", $VisionSampleMs)
}
if ($VisionMinDurationMs) {
    $args += @("--vision-min-duration-ms", $VisionMinDurationMs)
}
if ($NoKeepFiles) {
    $args += "--no-keep-files"
}
if ($JsonOutput) {
    $args += "--json"
}

Push-Location $repoRoot
try {
    $env:PYTHONUTF8 = "1"
    python -c "from app.services.dependency_bootstrap import ensure_opencv_dependency; ensure_opencv_dependency(raise_on_failure=False)" | Out-Null
    python @args
} finally {
    Pop-Location
}

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
$resolvedFfmpeg = if (Get-Command python -ErrorAction SilentlyContinue) {
    try {
        $env:PYTHONUTF8 = "1"
        (& python -c "from app.config import load_settings; print(load_settings().ffmpeg_bin)" 2>$null | Out-String).Trim()
    } catch {
        $null
    }
} else {
    $null
}

function Write-ResultJson {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Payload
    )
    $Payload | ConvertTo-Json -Depth 8
}

switch ($Action) {
    "doctor" {
        & "$PSScriptRoot\\doctor.ps1"
    }
    "paths" {
        Write-ResultJson @{
            action = "paths"
            repo_root = $repoRoot
            scripts = @{
                vivid_tool = (Join-Path $PSScriptRoot "vivid_tool.ps1")
                vivid_tool_sh = (Join-Path $PSScriptRoot "vivid_tool.sh")
                doctor = (Join-Path $PSScriptRoot "doctor.ps1")
                doctor_sh = (Join-Path $PSScriptRoot "doctor.sh")
                run_quickread = (Join-Path $PSScriptRoot "run_quickread.ps1")
                run_quickread_sh = (Join-Path $PSScriptRoot "run_quickread.sh")
                run_web_ui = (Join-Path $PSScriptRoot "run_web_ui.ps1")
                run_web_ui_sh = (Join-Path $PSScriptRoot "run_web_ui.sh")
                manage_vision = (Join-Path $PSScriptRoot "manage_vision.ps1")
                manage_vision_sh = (Join-Path $PSScriptRoot "manage_vision.sh")
                manage_transcription = (Join-Path $PSScriptRoot "manage_transcription.ps1")
                manage_transcription_sh = (Join-Path $PSScriptRoot "manage_transcription.sh")
            }
            skill = @{
                root = (Join-Path $repoRoot "skill\\vivid-operator")
                skill_md = (Join-Path $repoRoot "skill\\vivid-operator\\SKILL.md")
                wrapper_sh = (Join-Path $repoRoot "skill\\vivid-operator\\scripts\\vivid_operator.sh")
            }
            data = @{
                default_root = if ($env:VIVID_DATA_DIR) { $env:VIVID_DATA_DIR } else { (Join-Path $repoRoot "data") }
            }
            runtime = @{
                ffmpeg_bin = if ($resolvedFfmpeg) { $resolvedFfmpeg } elseif ($env:VIVID_FFMPEG_BIN) { $env:VIVID_FFMPEG_BIN } else { "ffmpeg" }
                whisper_root = $env:VIVID_WHISPER_ROOT
                acquisition_mode = if ($env:VIVID_ACQUISITION_MODE) { $env:VIVID_ACQUISITION_MODE } else { "auto" }
                transcription_backend = if ($env:VIVID_TRANSCRIPTION_BACKEND) { $env:VIVID_TRANSCRIPTION_BACKEND } else { "auto" }
                vision_backend = if ($env:VIVID_VISION_BACKEND) { $env:VIVID_VISION_BACKEND } else { "auto" }
            }
            configs = @{
                vision = @{
                    root = (Join-Path $repoRoot "configs\\vision")
                    api_configs = if ($env:VIVID_VISION_API_CONFIGS_FILE) { $env:VIVID_VISION_API_CONFIGS_FILE } else { (Join-Path $repoRoot "configs\\vision\\api_configs.json") }
                    prompts = if ($env:VIVID_VISION_PROMPTS_FILE) { $env:VIVID_VISION_PROMPTS_FILE } else { (Join-Path $repoRoot "configs\\vision\\prompts.json") }
                }
                transcription = @{
                    root = (Join-Path $repoRoot "configs\\transcription")
                    presets = if ($env:VIVID_TRANSCRIPTION_PRESETS_FILE) { $env:VIVID_TRANSCRIPTION_PRESETS_FILE } else { (Join-Path $repoRoot "configs\\transcription\\presets.json") }
                }
            }
            subsystems = @{
                vision = (Join-Path $repoRoot "app\\subsystems\\vision")
                transcription = (Join-Path $repoRoot "app\\subsystems\\transcription")
            }
            tools = @{
                downloader = @{
                    bilibili = "bili-downloader-agent"
                    douyin = "douyin-download-1.2.0"
                    generic = "yt_dlp_python"
                }
                helper_scripts_required = $true
                helper_paths = @{
                    bili = if ($env:VIVID_BILI_SCRIPT) { $env:VIVID_BILI_SCRIPT } else { (Join-Path (Split-Path -Parent $repoRoot) "bili-downloader-agent\\bili-downloader-agent\\scripts\\bili23_agent_cli.py") }
                    douyin = if ($env:VIVID_DOUYIN_SCRIPT) { $env:VIVID_DOUYIN_SCRIPT } else { (Join-Path (Split-Path -Parent $repoRoot) "douyin-download-1.2.0\\douyin.js") }
                }
            }
        }
    }
    "quickread" {
        if (-not $Source) {
            throw "Source is required for quickread."
        }
        $commandOutput = $null
        $commandError = $null
        $exitCode = 0
        $runArgs = @{
            Source = $Source
            Format = $Format
            JsonOutput = $true
            NoKeepFiles = $NoKeepFiles
        }
        if ($ProjectName) { $runArgs.ProjectName = $ProjectName }
        if ($DataDir) { $runArgs.DataDir = $DataDir }
        if ($Platform) { $runArgs.Platform = $Platform }
        if ($Model) { $runArgs.Model = $Model }
        if ($FfmpegBin) { $runArgs.FfmpegBin = $FfmpegBin }
        if ($WhisperRoot) { $runArgs.WhisperRoot = $WhisperRoot }
        if ($AcquisitionMode) { $runArgs.AcquisitionMode = $AcquisitionMode }
        if ($PreferOcr) { $runArgs.PreferOcr = $PreferOcr }
        if ($ForceOcr) { $runArgs.ForceOcr = $ForceOcr }
        if ($TranscriptionBackend) { $runArgs.TranscriptionBackend = $TranscriptionBackend }
        if ($VisionBackend) { $runArgs.VisionBackend = $VisionBackend }
        if ($TranscribeTimeout) { $runArgs.TranscribeTimeout = $TranscribeTimeout }
        if ($OcrTimeout) { $runArgs.OcrTimeout = $OcrTimeout }
        if ($VisionApiConfigId) { $runArgs.VisionApiConfigId = $VisionApiConfigId }
        if ($VisionTimeout) { $runArgs.VisionTimeout = $VisionTimeout }
        if ($VisionSampleMs) { $runArgs.VisionSampleMs = $VisionSampleMs }
        if ($VisionMinDurationMs) { $runArgs.VisionMinDurationMs = $VisionMinDurationMs }

        try {
            $commandOutput = & "$PSScriptRoot\\run_quickread.ps1" @runArgs 2>&1
            $exitCode = $LASTEXITCODE
        } catch {
            $commandError = $_.Exception.Message
            $exitCode = 1
        }

        $stdout = if ($commandOutput) { (($commandOutput | Out-String).Trim()) } else { "" }
        $parsed = $null

        if ($stdout) {
            try {
                $parsed = $stdout | ConvertFrom-Json
            } catch {
                $parsed = $null
            }
        }

        Write-ResultJson @{
            action = "quickread"
            ok = ($exitCode -eq 0)
            source = $Source
            project_name = $ProjectName
            format = $Format
            data_dir = $DataDir
            platform = $Platform
            model = $Model
            no_keep_files = [bool]$NoKeepFiles
            exit_code = $exitCode
            result = $parsed
            raw_output = if ($parsed) { $null } else { $stdout }
            error = $commandError
            ffmpeg_bin = $FfmpegBin
            whisper_root = $WhisperRoot
            acquisition_mode = $AcquisitionMode
            prefer_ocr = [bool]$PreferOcr
            force_ocr = [bool]$ForceOcr
            transcription_backend = $TranscriptionBackend
            vision_backend = $VisionBackend
            transcribe_timeout = $TranscribeTimeout
            ocr_timeout = $OcrTimeout
            vision_api_config_id = $VisionApiConfigId
            vision_timeout = $VisionTimeout
            vision_sample_ms = $VisionSampleMs
            vision_min_duration_ms = $VisionMinDurationMs
        }
    }
    "web-ui" {
        & "$PSScriptRoot\\run_web_ui.ps1" -Host $UiHost -Port $Port
    }
    "vision-configs" {
        & "$PSScriptRoot\\manage_vision.ps1" -Command list-configs
    }
    "vision-prompts" {
        & "$PSScriptRoot\\manage_vision.ps1" -Command list-prompts
    }
    "vision-select-config" {
        if (-not $Id) {
            throw "Id is required for vision-select-config."
        }
        & "$PSScriptRoot\\manage_vision.ps1" -Command select-config -Id $Id
    }
    "vision-upsert-config" {
        if (-not $Id -or -not $Name -or -not $ApiBase) {
            throw "Id, Name, and ApiBase are required for vision-upsert-config."
        }
        & "$PSScriptRoot\\manage_vision.ps1" `
            -Command upsert-config `
            -Id $Id `
            -Name $Name `
            -ApiBase $ApiBase `
            -ApiPath $ApiPath `
            -Model $Model `
            -Timeout $Timeout `
            -Group $Group `
            -Note $Note `
            -Prompt $Prompt `
            -SystemPrompt $SystemPrompt `
            -ApiKeyEnv $ApiKeyEnv
    }
    "vision-upsert-prompt" {
        if (-not $Id -or -not $Name -or -not $Content) {
            throw "Id, Name, and Content are required for vision-upsert-prompt."
        }
        & "$PSScriptRoot\\manage_vision.ps1" `
            -Command upsert-prompt `
            -Id $Id `
            -Name $Name `
            -Content $Content
    }
    "transcription-presets" {
        & "$PSScriptRoot\\manage_transcription.ps1" -Command list-presets
    }
    "transcription-select-preset" {
        if (-not $Id) {
            throw "Id is required for transcription-select-preset."
        }
        & "$PSScriptRoot\\manage_transcription.ps1" -Command select-preset -Id $Id
    }
    "transcription-upsert-preset" {
        if (-not $Id -or -not $Name) {
            throw "Id and Name are required for transcription-upsert-preset."
        }
        & "$PSScriptRoot\\manage_transcription.ps1" `
            -Command upsert-preset `
            -Id $Id `
            -Name $Name `
            -Model $Model `
            -Device $Device `
            -Language $Language `
            -Task $Task `
            -ExtractAudio:$ExtractAudio `
            -NoExtractAudio:$NoExtractAudio `
            -Note $Note
    }
}

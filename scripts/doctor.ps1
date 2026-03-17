param()

$repoRoot = Split-Path -Parent $PSScriptRoot
$toolsRoot = Split-Path -Parent $repoRoot
$checks = [ordered]@{
    python = $null
    node = $null
    ffmpeg = $null
    requests = $null
    yt_dlp_python = $null
    whisper = $null
    torch = $null
    opencv = $null
    vivid_data_dir = $null
    ffmpeg_bin = $null
    whisper_root = $null
    acquisition_mode = $null
    transcription_backend = $null
    vision_backend = $null
    ears4_api = $null
    eyes_api = $null
    bili_helper = $null
    douyin_helper = $null
    vision_configs = $null
    transcription_configs = $null
}

$python = Get-Command python -ErrorAction SilentlyContinue
$node = Get-Command node -ErrorAction SilentlyContinue
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
$biliHelper = if ($env:VIVID_BILI_SCRIPT) { $env:VIVID_BILI_SCRIPT } else { Join-Path $toolsRoot "bili-downloader-agent\bili-downloader-agent\scripts\bili23_agent_cli.py" }
$douyinHelper = if ($env:VIVID_DOUYIN_SCRIPT) { $env:VIVID_DOUYIN_SCRIPT } else { Join-Path $toolsRoot "douyin-download-1.2.0\douyin.js" }
$visionApiConfigs = if ($env:VIVID_VISION_API_CONFIGS_FILE) { $env:VIVID_VISION_API_CONFIGS_FILE } else { Join-Path $repoRoot "configs\vision\api_configs.json" }
$visionPrompts = if ($env:VIVID_VISION_PROMPTS_FILE) { $env:VIVID_VISION_PROMPTS_FILE } else { Join-Path $repoRoot "configs\vision\prompts.json" }
$transcriptionPresets = if ($env:VIVID_TRANSCRIPTION_PRESETS_FILE) { $env:VIVID_TRANSCRIPTION_PRESETS_FILE } else { Join-Path $repoRoot "configs\transcription\presets.json" }

$checks.python = [ordered]@{
    available = [bool]$python
    path = if ($python) { $python.Source } else { $null }
}
$checks.node = [ordered]@{
    available = [bool]$node
    path = if ($node) { $node.Source } else { $null }
}
$checks.ffmpeg = [ordered]@{
    available = [bool]$ffmpeg
    path = if ($ffmpeg) { $ffmpeg.Source } else { $null }
}
$checks.requests = [ordered]@{
    available = $false
}
$checks.yt_dlp_python = [ordered]@{
    available = $false
}
$checks.whisper = [ordered]@{
    available = $false
}
$checks.torch = [ordered]@{
    available = $false
}
$checks.opencv = [ordered]@{
    available = $false
}
$checks.vivid_data_dir = [ordered]@{
    path = if ($env:VIVID_DATA_DIR) { $env:VIVID_DATA_DIR } else { ".\\data" }
}
$checks.ffmpeg_bin = [ordered]@{
    value = if ($env:VIVID_FFMPEG_BIN) { $env:VIVID_FFMPEG_BIN } else { "ffmpeg" }
}
$checks.whisper_root = [ordered]@{
    value = $env:VIVID_WHISPER_ROOT
    exists = if ($env:VIVID_WHISPER_ROOT) { Test-Path $env:VIVID_WHISPER_ROOT } else { $null }
}
$checks.acquisition_mode = [ordered]@{
    value = if ($env:VIVID_ACQUISITION_MODE) { $env:VIVID_ACQUISITION_MODE } else { "auto" }
}
$checks.transcription_backend = [ordered]@{
    value = if ($env:VIVID_TRANSCRIPTION_BACKEND) { $env:VIVID_TRANSCRIPTION_BACKEND } else { "auto" }
}
$checks.vision_backend = [ordered]@{
    value = if ($env:VIVID_VISION_BACKEND) { $env:VIVID_VISION_BACKEND } else { "auto" }
}
$checks.ears4_api = [ordered]@{
    url = if ($env:EARS4_API) { $env:EARS4_API } else { "http://127.0.0.1:7860" }
}
$checks.eyes_api = [ordered]@{
    url = if ($env:EYES_API) { $env:EYES_API } else { "http://127.0.0.1:9531" }
}
$checks.bili_helper = [ordered]@{
    exists = Test-Path $biliHelper
    path = $biliHelper
}
$checks.douyin_helper = [ordered]@{
    exists = Test-Path $douyinHelper
    path = $douyinHelper
}
$checks.vision_configs = [ordered]@{
    api_configs = [ordered]@{
        exists = Test-Path $visionApiConfigs
        path = $visionApiConfigs
    }
    prompts = [ordered]@{
        exists = Test-Path $visionPrompts
        path = $visionPrompts
    }
}
$checks.transcription_configs = [ordered]@{
    presets = [ordered]@{
        exists = Test-Path $transcriptionPresets
        path = $transcriptionPresets
    }
}

if ($python) {
    $env:PYTHONUTF8 = "1"
    $ffmpegInfoJson = & python -c "from app.config import load_settings; from app.services.ffmpeg_locator import inspect_ffmpeg; import json; s=load_settings(); print(json.dumps(inspect_ffmpeg(preferred=None, repo_root=s.repo_root, tools_root=s.tools_root), ensure_ascii=False))" 2>$null
    $requestsCheck = & python -c "import importlib.util; print('1' if importlib.util.find_spec('requests') else '0')" 2>$null
    $ytdlpCheck = & python -c "import importlib.util; print('1' if importlib.util.find_spec('yt_dlp') else '0')" 2>$null
    $whisperCheck = & python -c "import importlib.util; print('1' if importlib.util.find_spec('whisper') else '0')" 2>$null
    $torchCheck = & python -c "import importlib.util; print('1' if importlib.util.find_spec('torch') else '0')" 2>$null
    $opencvInfoJson = & python -c "from app.services.dependency_bootstrap import ensure_opencv_dependency; import json; print(json.dumps(ensure_opencv_dependency(raise_on_failure=False), ensure_ascii=False))" 2>$null
    if ($ffmpegInfoJson) {
        $ffmpegInfo = $ffmpegInfoJson | ConvertFrom-Json
        $checks.ffmpeg = [ordered]@{
            available = [bool]$ffmpegInfo.available
            path = $ffmpegInfo.resolved
            source = $ffmpegInfo.source
            candidates = $ffmpegInfo.candidates
        }
    }
    $checks.requests.available = (($requestsCheck | Out-String).Trim() -eq "1")
    $checks.yt_dlp_python.available = (($ytdlpCheck | Out-String).Trim() -eq "1")
    $checks.whisper.available = (($whisperCheck | Out-String).Trim() -eq "1")
    $checks.torch.available = (($torchCheck | Out-String).Trim() -eq "1")
    if ($opencvInfoJson) {
        $opencvInfo = $opencvInfoJson | ConvertFrom-Json
        $checks.opencv = [ordered]@{
            available = [bool]$opencvInfo.ok
            package = $opencvInfo.package
            installed = $opencvInfo.installed
            already_available = $opencvInfo.already_available
            index_url = $opencvInfo.index_url
        }
    }
}

[ordered]@{
    action = "doctor"
    ok = [bool](
        $checks.python.available `
        -and $checks.node.available `
        -and $checks.ffmpeg.available `
        -and $checks.requests.available `
        -and $checks.whisper.available `
        -and $checks.torch.available `
        -and $checks.opencv.available `
        -and $checks.bili_helper.exists `
        -and $checks.douyin_helper.exists
    )
    repo_root = $repoRoot
    tools_root = $toolsRoot
    checks = $checks
} | ConvertTo-Json -Depth 6

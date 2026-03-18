param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("list-configs", "list-prompts", "select-config", "upsert-config", "upsert-prompt")]
    [string]$Command,
    [string]$Id,
    [string]$Name,
    [string]$ApiBase,
    [string]$ApiPath = "/v1/chat/completions",
    [string]$Model,
    [int]$Timeout = 30,
    [string]$Group = "default",
    [string]$Note,
    [string]$Prompt,
    [string]$SystemPrompt,
    [string]$ApiKeyEnv,
    [string]$Content,
    [string]$ApiConfigsFile,
    [string]$PromptsFile
)

$repoRoot = Split-Path -Parent $PSScriptRoot

# Ensure the runtime virtual environment exists.
$venvPython = & "$PSScriptRoot\ensure_venv.ps1" -RepoRoot $repoRoot
if (-not $venvPython) {
    Write-Error "Could not resolve the virtual environment Python executable."
    exit 1
}

$apiConfigs = if ($ApiConfigsFile) { $ApiConfigsFile } elseif ($env:VIVID_VISION_API_CONFIGS_FILE) { $env:VIVID_VISION_API_CONFIGS_FILE } else { Join-Path $repoRoot "configs\vision\api_configs.json" }
$prompts = if ($PromptsFile) { $PromptsFile } elseif ($env:VIVID_VISION_PROMPTS_FILE) { $env:VIVID_VISION_PROMPTS_FILE } else { Join-Path $repoRoot "configs\vision\prompts.json" }

$args = @(
    "-m", "app.tools.vision_admin",
    "--api-configs-file", $apiConfigs,
    "--prompts-file", $prompts,
    $Command
)

switch ($Command) {
    "select-config" {
        $args += @("--id", $Id)
    }
    "upsert-config" {
        $args += @("--id", $Id, "--name", $Name, "--api-base", $ApiBase, "--api-path", $ApiPath, "--timeout", "$Timeout", "--group", $Group)
        if ($Model) { $args += @("--model", $Model) }
        if ($Note) { $args += @("--note", $Note) }
        if ($Prompt) { $args += @("--prompt", $Prompt) }
        if ($SystemPrompt) { $args += @("--system-prompt", $SystemPrompt) }
        if ($ApiKeyEnv) { $args += @("--api-key-env", $ApiKeyEnv) }
    }
    "upsert-prompt" {
        $args += @("--id", $Id, "--name", $Name, "--content", $Content)
    }
}

Push-Location $repoRoot
try {
    & $venvPython @args
} finally {
    Pop-Location
}

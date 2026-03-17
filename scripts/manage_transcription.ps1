param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("list-presets", "select-preset", "upsert-preset")]
    [string]$Command,
    [string]$Id,
    [string]$Name,
    [string]$Model = "base",
    [string]$Device = "auto",
    [string]$Language = "zh",
    [string]$Task = "transcribe",
    [switch]$ExtractAudio,
    [switch]$NoExtractAudio,
    [string]$Note,
    [string]$PresetsFile
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$presets = if ($PresetsFile) { $PresetsFile } elseif ($env:VIVID_TRANSCRIPTION_PRESETS_FILE) { $env:VIVID_TRANSCRIPTION_PRESETS_FILE } else { Join-Path $repoRoot "configs\\transcription\\presets.json" }

$args = @(
    "-m", "app.tools.transcription_admin",
    "--presets-file", $presets,
    $Command
)

switch ($Command) {
    "select-preset" {
        $args += @("--id", $Id)
    }
    "upsert-preset" {
        $args += @("--id", $Id, "--name", $Name, "--model", $Model, "--device", $Device, "--language", $Language, "--task", $Task)
        if ($ExtractAudio) { $args += "--extract-audio" }
        if ($NoExtractAudio) { $args += "--no-extract-audio" }
        if ($Note) { $args += @("--note", $Note) }
    }
}

Push-Location $repoRoot
try {
    python @args
} finally {
    Pop-Location
}

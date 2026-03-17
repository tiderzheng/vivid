param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("doctor", "quickread")]
    [string]$Action,
    [string]$Source,
    [string]$ProjectName,
    [string]$Format = "both"
)

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$tool = Join-Path $repoRoot "scripts\\vivid_tool.ps1"

& $tool -Action $Action -Source $Source -ProjectName $ProjectName -Format $Format

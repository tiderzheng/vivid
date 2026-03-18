param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("doctor", "quickread", "paths", "web-ui")]
    [string]$Action,
    [string]$Source,
    [string]$ProjectName,
    [string]$Format = "both",
    [string]$Sessdata,
    [switch]$NoSessdata,
    [string]$VividRoot = $env:VIVID_REPO_ROOT
)

if ($VividRoot) {
    $repoRoot = $VividRoot
    Write-Host "Using VIVID_REPO_ROOT: $repoRoot" -ForegroundColor Green
} else {
    $detectedRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
    $toolPath = Join-Path $detectedRoot "scripts\vivid_tool.ps1"
    if (Test-Path $toolPath) {
        $repoRoot = $detectedRoot
        Write-Host "Detected Vivid repository: $repoRoot" -ForegroundColor Green
    } else {
        Write-Host "Error: could not locate the Vivid repository." -ForegroundColor Red
        Write-Host ""
        Write-Host "Provide the repository location in one of these ways:" -ForegroundColor Yellow
        Write-Host "  1. Set VIVID_REPO_ROOT, for example: `$env:VIVID_REPO_ROOT = 'C:\path\to\vivid'" -ForegroundColor Cyan
        Write-Host "  2. Pass -VividRoot 'C:\path\to\vivid'" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "The skill auto-detects correctly when it is kept under skill/vivid-operator/ inside the Vivid repo." -ForegroundColor Yellow
        exit 1
    }
}

$tool = Join-Path $repoRoot "scripts\vivid_tool.ps1"
if (-not (Test-Path $tool)) {
    Write-Host "Error: could not find the Vivid entrypoint: $tool" -ForegroundColor Red
    exit 1
}

$invokeArgs = @{
    Action = $Action
}
if ($Source) { $invokeArgs.Source = $Source }
if ($ProjectName) { $invokeArgs.ProjectName = $ProjectName }
if ($Format) { $invokeArgs.Format = $Format }
if ($Sessdata) { $invokeArgs.Sessdata = $Sessdata }
if ($NoSessdata) { $invokeArgs.NoSessdata = $true }

& $tool @invokeArgs
exit $LASTEXITCODE

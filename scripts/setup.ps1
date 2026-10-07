param(
    [string]$VectorCraftCli
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
$HoardLink = $env:HOARDLINK_DIR
if (-not $HoardLink) {
    $HoardLink = Join-Path (Split-Path -Parent $Root) 'HoardLink'
}
if (-not (Test-Path (Join-Path $HoardLink 'pyproject.toml'))) {
    throw "HoardLink checkout not found at '$HoardLink'. Set HOARDLINK_DIR to its local checkout."
}

if (-not (Test-Path $VenvPython)) { py -3 -m venv (Join-Path $Root '.venv') }
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e $Root
& $VenvPython -m pip install -e $HoardLink

$Configure = Join-Path $Root 'scripts\configure.py'
if ($VectorCraftCli) {
    & $VenvPython $Configure $VectorCraftCli
} else {
    & $VenvPython $Configure
}
& $VenvPython -m pip install -e '.[dev]'
Write-Host 'Setup complete. Run scripts\launch.ps1'

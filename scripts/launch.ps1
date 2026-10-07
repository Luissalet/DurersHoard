$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Run scripts\setup.ps1 first.' }
Push-Location $Root
try { & $Python (Join-Path $Root 'scripts\launch.py') } finally { Pop-Location }

# Lint apps and shared. Run from repo root.
# Optional: pip install ruff; ruff check shared apps
$root = if ($PSScriptRoot) { Split-Path $PSScriptRoot -Parent } else { ".." }
Set-Location $root
Write-Host "Lint: run 'ruff check shared common shared db apps' if ruff is installed"

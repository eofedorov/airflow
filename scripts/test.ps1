# Run tests for shared and apps. Run from repo root.
$root = if ($PSScriptRoot) { Split-Path $PSScriptRoot -Parent } else { ".." }
Set-Location $root

# Install deps if needed: pip install -e shared/common -e shared/db, then per-app
$env:PYTHONPATH = "shared/common/src;shared/db/src"
# Gateway tests (when added)
# Set-Location apps/gateway; python -m pytest tests -q; Set-Location $root
# MCP server tests (when added)
# Set-Location apps/mcp_server; $env:PYTHONPATH = "..\..\shared\common\src;..\..\shared\db\src;src"; python -m pytest tests -q; Set-Location $root
Write-Host "Tests: run pytest from each app (apps/gateway, apps/mcp_server) with PYTHONPATH including shared"

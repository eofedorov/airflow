# Start compose: postgres, qdrant, mcp-server.
# Run from repo root.
Set-Location $PSScriptRoot\..
docker compose -f compose.yaml up -d

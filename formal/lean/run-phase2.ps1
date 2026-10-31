param([string]$OutputPath = "work\phase2-lean-dependencies.json")

& (Join-Path $PSScriptRoot "run-extraction.ps1") `
    -NodeSet "data\mathematics\phase2-nodes.json" `
    -OutputPath $OutputPath
exit $LASTEXITCODE

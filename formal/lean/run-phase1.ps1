param([string]$OutputPath = "work\phase1-lean-dependencies.json")

& (Join-Path $PSScriptRoot "run-extraction.ps1") `
    -NodeSet "data\mathematics\phase1-nodes.json" `
    -OutputPath $OutputPath
exit $LASTEXITCODE

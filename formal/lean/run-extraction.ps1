param(
    [Parameter(Mandatory = $true)]
    [string]$NodeSet,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$NodeSet = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $NodeSet))
$OutputPath = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $OutputPath))
$OutputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$Selection = Get-Content -LiteralPath $NodeSet -Raw -Encoding utf8 | ConvertFrom-Json
$Mappings = (Get-Content -LiteralPath (Join-Path $RepoRoot "data\mathematics\mappings.json") -Raw -Encoding utf8 | ConvertFrom-Json).mappings
$Declarations = (Get-Content -LiteralPath (Join-Path $RepoRoot "data\mathematics\declarations.json") -Raw -Encoding utf8 | ConvertFrom-Json).declarations
$Selected = @{}
foreach ($NodeId in $Selection.nodes) { $Selected[$NodeId] = $true }
$DeclarationName = @{}
foreach ($Declaration in $Declarations) { $DeclarationName[$Declaration.id] = $Declaration.name }
$Targets = $Mappings |
    Where-Object { $Selected.ContainsKey($_.node_id) -and $_.review_status -ne "candidate" } |
    ForEach-Object { $DeclarationName[$_.declaration_id] } |
    Sort-Object -Unique
if (-not $Targets) { throw "The selected node set has no reviewed declaration anchors." }

$LocalLean = Join-Path $RepoRoot "work\lean\elan\toolchains\leanprover--lean4---v4.36.0-rc2\bin\lean.exe"
if (Test-Path -LiteralPath $LocalLean) {
    $LeanExe = $LocalLean
} else {
    $LeanCommand = Get-Command lean -ErrorAction SilentlyContinue
    if (-not $LeanCommand) {
        throw "Lean was not found. Install the toolchain from formal/lean/lean-toolchain first."
    }
    $LeanExe = $LeanCommand.Source
}

$PackageRoot = Join-Path $PSScriptRoot ".lake\packages"
$MathlibOlean = Join-Path $PackageRoot "mathlib\.lake\build\lib\lean"
if (-not (Test-Path -LiteralPath $MathlibOlean)) {
    throw "mathlib oleans are missing. Run 'lake update' and 'lake exe cache get' in formal/lean first."
}

$ProjectOlean = Join-Path $PSScriptRoot ".lake\build\lib\lean"
$ProjectNamespace = Join-Path $ProjectOlean "KnowledgeGalaxy"
New-Item -ItemType Directory -Path $ProjectNamespace -Force | Out-Null
$LibraryPaths = @($ProjectOlean)
$LibraryPaths += Get-ChildItem -LiteralPath $PackageRoot -Directory | ForEach-Object {
    Join-Path $_.FullName ".lake\build\lib\lean"
} | Where-Object { Test-Path -LiteralPath $_ }
$env:LEAN_PATH = $LibraryPaths -join [System.IO.Path]::PathSeparator

Push-Location $PSScriptRoot
try {
    & $LeanExe -o ".lake\build\lib\lean\KnowledgeGalaxy\PhaseOneImports.olean" "KnowledgeGalaxy\PhaseOneImports.lean"
    if ($LASTEXITCODE -ne 0) { throw "PhaseOneImports.lean compilation failed." }
    & $LeanExe -o ".lake\build\lib\lean\KnowledgeGalaxy\PhaseTwoImports.olean" "KnowledgeGalaxy\PhaseTwoImports.lean"
    if ($LASTEXITCODE -ne 0) { throw "PhaseTwoImports.lean compilation failed." }
    & $LeanExe -o ".lake\build\lib\lean\KnowledgeGalaxy\ExtractDependencies.olean" "KnowledgeGalaxy\ExtractDependencies.lean"
    if ($LASTEXITCODE -ne 0) { throw "ExtractDependencies.lean compilation failed." }
    & $LeanExe --run "Main.lean" $OutputPath $Selection.experiment @Targets
    if ($LASTEXITCODE -ne 0) { throw "Lean dependency extraction failed." }
} finally {
    Pop-Location
}

Write-Output "Lean dependency extraction written to $OutputPath ($($Targets.Count) declaration anchors)"

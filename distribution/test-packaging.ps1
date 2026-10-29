param(
    [Parameter(Mandatory=$true)][string]$SourceZip,
    [Parameter(Mandatory=$true)][string]$SourceSha256,
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Destination) { throw 'Test destination must be NEW.' }
$null = New-Item -ItemType Directory -Path $Destination
$root = (Resolve-Path -LiteralPath $Destination).Path
function Reject([scriptblock]$Action) {
    $failed = $false
    try { & $Action } catch { $failed = $true }
    if (-not $failed) { throw 'Expected rejection did not occur.' }
}
$url = 'https://github.com/afkDen/PPL_Group1_LexicalAnalyzer/releases/download/lexical-static-dfa-final-2026-10-30/Ternfold_Lexical_Static_DFA_Source_2026-10-30.zip'
& "$PSScriptRoot/validate-input.ps1" -SourceZipUrl $url -SourceSha256 $SourceSha256
Reject { & "$PSScriptRoot/validate-input.ps1" -SourceZipUrl ($url + '?query=1') -SourceSha256 $SourceSha256 }
Reject { & "$PSScriptRoot/validate-input.ps1" -SourceZipUrl 'https://example.org/source.zip' -SourceSha256 $SourceSha256 }
Reject { & "$PSScriptRoot/validate-input.ps1" -SourceZipUrl $url -SourceSha256 'bad' }
Reject { & "$PSScriptRoot/source-check.ps1" -SourceZip $SourceZip -SourceSha256 ('0' * 64) }
& "$PSScriptRoot/prepare.ps1" -SourceZip $SourceZip -SourceSha256 $SourceSha256 -Destination "$root/payload"
Reject { & "$PSScriptRoot/prepare.ps1" -SourceZip $SourceZip -SourceSha256 $SourceSha256 -Destination "$root/payload" }
Set-Content -LiteralPath "$root/payload/.private" -Value 'private'
Reject { & "$PSScriptRoot/manifest.ps1" -Root "$root/payload" -ValidateOnly }
foreach ($path in @('src/name_dfa.inc','../escape','.private','SOURCE_FILES.txt')) {
    $mutated = Join-Path $root ([guid]::NewGuid().ToString() + '.zip')
    Copy-Item -LiteralPath $SourceZip -Destination $mutated
    $zip = [IO.Compression.ZipFile]::Open($mutated, [IO.Compression.ZipArchiveMode]::Update)
    try { $entry = $zip.CreateEntry($path); $stream = $entry.Open(); $stream.Dispose() }
    finally { $zip.Dispose() }
    $hash = (Get-FileHash -LiteralPath $mutated).Hash
    Reject { & "$PSScriptRoot/source-check.ps1" -SourceZip $mutated -SourceSha256 $hash }
}
Set-Content -LiteralPath "$root/payload/source/src/name_dfa.inc" -Value 'changed'
Reject { & "$PSScriptRoot/source-check.ps1" -SourceZip $SourceZip -SourceSha256 $SourceSha256 -SourceRoot "$root/payload/source" }
Write-Output 'PASS: explicit inputs, wrong pin, duplicate/traversal/private ZIP entries, source mutation, payload privacy, new-destination checks.'

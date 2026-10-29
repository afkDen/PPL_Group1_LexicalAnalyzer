param(
    [Parameter(Mandatory=$true)][string]$SourceZip,
    [Parameter(Mandatory=$true)][string]$SourceSha256,
    [Parameter(Mandatory=$true)][string]$PriorBundle,
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Destination) { throw 'Test destination must be NEW.' }
$null = New-Item -ItemType Directory -Path $Destination
$root = (Resolve-Path -LiteralPath $Destination).Path
Add-Type -AssemblyName System.IO.Compression.FileSystem
function Reject([scriptblock]$Action, [string]$Reason) {
    $caught = $null
    try { & $Action } catch { $caught = $_ }
    if (-not $caught -or $caught.Exception.Message -notmatch $Reason) { throw "Expected rejection matching '$Reason'; got '$caught'." }
}
function Mutate([string]$Path, [string]$Entry) {
    Copy-Item -LiteralPath $SourceZip -Destination $Path
    $zip = [IO.Compression.ZipFile]::Open($Path, [IO.Compression.ZipArchiveMode]::Update)
    try {
        $entryObject = $zip.GetEntry($Entry)
        if (-not $entryObject) { throw "Missing fixture entry: $Entry" }
        $stream = $entryObject.Open()
        try {
            $stream.Seek(0, [IO.SeekOrigin]::End) | Out-Null
            $bytes = [Text.Encoding]::UTF8.GetBytes("`n/* repack identity test */`n")
            $stream.Write($bytes, 0, $bytes.Length)
        } finally { $stream.Dispose() }
    } finally { $zip.Dispose() }
}
& "$PSScriptRoot/prepare-repack.ps1" -SourceZip $SourceZip -SourceSha256 $SourceSha256 -PriorBundle $PriorBundle -Destination "$root/accepted"
if ((Get-Content "$root/accepted/README.md" -Raw) -notmatch ([regex]::Escape($SourceSha256.ToLowerInvariant()))) { throw 'Generated root README lacks embedded source hash.' }
& "$PSScriptRoot/source-check.ps1" -SourceZip $SourceZip -SourceSha256 $SourceSha256 -SourceRoot "$root/accepted/source"
$historical = [IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $PriorBundle).Path)
try {
    foreach ($entry in $historical.Entries | Where-Object { $_.FullName -match '^licenses/.+[^/]$|^bin/[^/]+/ternfold-lexer(\.exe)?$' }) {
        $stream = $entry.Open(); $sha = [Security.Cryptography.SHA256]::Create()
        try { $digest = ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','') }
        finally { $stream.Dispose(); $sha.Dispose() }
        if ((Get-FileHash -LiteralPath (Join-Path "$root/accepted" $entry.FullName)).Hash -ne $digest) { throw "Accepted binary/license differs from prior ZIP: $($entry.FullName)" }
    }
} finally { $historical.Dispose() }
foreach ($record in Get-ChildItem "$root/accepted/bin" -File -Recurse -Filter '*.txt') {
    if ([IO.File]::ReadAllText($record.FullName) -match '/Users/runner/') { throw 'Build record leaked a runner path.' }
}
Reject { & "$PSScriptRoot/prepare-repack.ps1" -SourceZip $SourceZip -SourceSha256 $SourceSha256 -PriorBundle $PriorBundle -Destination "$root/accepted" } 'Destination must be NEW'
Reject { & "$PSScriptRoot/prepare-repack.ps1" -SourceZip $SourceZip -SourceSha256 ('0' * 64) -PriorBundle $PriorBundle -Destination "$root/wrong-source" } 'Source ZIP SHA256 mismatch'
Set-Content -LiteralPath "$root/wrong-prior.zip" -Value 'not the accepted bundle'
Reject { & "$PSScriptRoot/prepare-repack.ps1" -SourceZip $SourceZip -SourceSha256 $SourceSha256 -PriorBundle "$root/wrong-prior.zip" -Destination "$root/wrong-prior" } 'Prior bundle SHA256 mismatch'
foreach ($entry in @('src/lexer.c','include/ternfold/lexer.h','src/name_dfa.inc')) {
    $zipPath = "$root/mutated-$([IO.Path]::GetFileName($entry)).zip"
    Mutate $zipPath $entry
    $hash = (Get-FileHash -LiteralPath $zipPath).Hash
    Reject { & "$PSScriptRoot/prepare-repack.ps1" -SourceZip $zipPath -SourceSha256 $hash -PriorBundle $PriorBundle -Destination "$root/rejected-$([IO.Path]::GetFileName($entry))" } 'Native source inventory or bytes changed'
}
# Documentation and a standalone audit-tool edit do not change production bins.
Mutate "$root/docs-only.zip" 'README.md'
$docsHash = (Get-FileHash "$root/docs-only.zip").Hash
& "$PSScriptRoot/prepare-repack.ps1" -SourceZip "$root/docs-only.zip" -SourceSha256 $docsHash -PriorBundle $PriorBundle -Destination "$root/docs-accepted"
Mutate "$root/audit-only.zip" 'tools/audit.c'
$auditHash = (Get-FileHash "$root/audit-only.zip").Hash
& "$PSScriptRoot/prepare-repack.ps1" -SourceZip "$root/audit-only.zip" -SourceSha256 $auditHash -PriorBundle $PriorBundle -Destination "$root/audit-accepted"
foreach ($file in Get-ChildItem "$root/accepted/bin","$root/accepted/licenses" -File -Recurse) {
    $relative = [IO.Path]::GetRelativePath("$root/accepted", $file.FullName)
    foreach ($other in @('docs-accepted','audit-accepted')) {
        if ((Get-FileHash -LiteralPath $file.FullName).Hash -ne (Get-FileHash -LiteralPath (Join-Path "$root/$other" $relative)).Hash) { throw "Repack changed preserved payload: $relative" }
    }
}
Write-Output 'PASS: exact production C/header/include identity, changed-production rejection, wrong source/prior pin rejection, new-destination boundary, docs/audit-only acceptance, unchanged binaries/licenses, embedded source hash.'

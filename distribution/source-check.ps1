param(
    [Parameter(Mandatory=$true)][string]$SourceZip,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$SourceSha256,
    [string]$SourceRoot
)
$ErrorActionPreference = 'Stop'
if ((Get-FileHash -LiteralPath $SourceZip -Algorithm SHA256).Hash -ine $SourceSha256) { throw 'Source ZIP SHA256 mismatch.' }
$allowlist = @(Get-Content -LiteralPath (Join-Path $PSScriptRoot '../SOURCE_FILES.txt'))
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($name in $allowlist) {
    if ($name -notmatch '^(?:[A-Za-z0-9_][A-Za-z0-9_ ./-]*|\.gitattributes|\.github/workflows/lexical-source\.yml)$' -or
        ($name -match '(^|/)\.\.?(/|$)|(^|/)\.[^/]+/' -and $name -ne '.github/workflows/lexical-source.yml') -or
        -not $seen.Add($name)) { throw "Unsafe or duplicate source allowlist path: $name" }
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $SourceZip).Path)
try {
    $entries = @($archive.Entries)
    if ($entries.Count -ne $allowlist.Count) { throw 'Source archive file count differs from SOURCE_FILES.txt.' }
    $found = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($entry in $entries) {
        if ($entry.FullName -cnotin $allowlist -or -not $found.Add($entry.FullName) -or
            (($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000) { throw "Unexpected/duplicate/link ZIP entry: $($entry.FullName)" }
    }
    $reader = [IO.StreamReader]::new($archive.GetEntry('SOURCE_FILES.txt').Open())
    try { $listed = @($reader.ReadToEnd() -split '\r?\n' | Where-Object { $_ -ne '' }) }
    finally { $reader.Dispose() }
    if (($listed -join [char]10) -cne ($allowlist -join [char]10)) { throw 'Embedded source allowlist differs from the checked source inventory.' }
    if ($SourceRoot) {
        $root = (Resolve-Path -LiteralPath $SourceRoot).Path
        $items = @(Get-ChildItem -LiteralPath $root -Recurse -Force)
        if (@($items | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw 'Source links are forbidden.' }
        $files = @($items | Where-Object { -not $_.PSIsContainer })
        if ($files.Count -ne $allowlist.Count) { throw 'Extracted source file count differs from allowlist.' }
        foreach ($entry in $entries) {
            $stream = $entry.Open(); $sha = [Security.Cryptography.SHA256]::Create()
            try { $expected = ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','') }
            finally { $stream.Dispose(); $sha.Dispose() }
            if ((Get-FileHash -LiteralPath (Join-Path $root $entry.FullName) -Algorithm SHA256).Hash -ne $expected) { throw "Source changed: $($entry.FullName)" }
        }
    }
} finally { $archive.Dispose() }
Write-Output "PASS: pinned source ZIP and $($allowlist.Count) allowlisted files."

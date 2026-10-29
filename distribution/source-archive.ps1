param(
    [Parameter(Mandatory=$true)][string]$Destination,
    [string]$SourceRoot = (Split-Path -Parent $PSScriptRoot)
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $SourceRoot).Path
if ((Test-Path -LiteralPath $Destination) -or (Test-Path -LiteralPath "$Destination.sha256")) { throw 'Source ZIP and sidecar destinations must be NEW.' }
$allowlist = @(Get-Content -LiteralPath (Join-Path $root 'SOURCE_FILES.txt'))
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($name in $allowlist) {
    if ($name -notmatch '^(?:[A-Za-z0-9_][A-Za-z0-9_ ./-]*|\.gitattributes|\.github/workflows/lexical-source\.yml)$' -or
        ($name -match '(^|/)\.\.?(/|$)|(^|/)\.[^/]+/' -and $name -ne '.github/workflows/lexical-source.yml') -or
        -not $seen.Add($name)) { throw "Unsafe or duplicate source allowlist path: $name" }
    $path = Join-Path $root $name
    $item = Get-Item -LiteralPath $path -Force
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Source file must be a regular file: $name" }
    $parent = $item.Directory
    while ($parent.FullName -ne $root) {
        if (($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) -or -not $parent.Parent) { throw "Source parent must be a real directory: $name" }
        $parent = $parent.Parent
    }
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::Open([IO.Path]::GetFullPath($Destination), [IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($name in $allowlist) {
        # Explicit entries retain dotfiles and avoid synthetic directory entries.
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, (Join-Path $root $name), $name, [IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
} finally { $archive.Dispose() }
$digest = (Get-FileHash -LiteralPath $Destination).Hash.ToLowerInvariant()
& "$PSScriptRoot/source-check.ps1" -SourceZip $Destination -SourceSha256 $digest
[IO.File]::WriteAllText([IO.Path]::GetFullPath("$Destination.sha256"), "$digest  $([IO.Path]::GetFileName($Destination))`n", [Text.UTF8Encoding]::new($false))
Write-Output "PASS: source archive contains all $($allowlist.Count) explicit allowlisted files; SHA-256 $digest."

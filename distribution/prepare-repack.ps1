param(
    [Parameter(Mandatory=$true)][string]$SourceZip,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$SourceSha256,
    [Parameter(Mandatory=$true)][string]$PriorBundle,
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
# These are immutable release identities, not caller-selected reuse candidates.
$priorHash = 'a105a379d16a63dc51e423ee49a8d954f75daae3c2ec09344e03d10050ec34ae'
$priorSourceHash = '110cfff05ec8b72812f40e9da6fef68b437859d299320848db578ecb3fbbadf1'
if ((Get-FileHash -LiteralPath $PriorBundle).Hash -ine $priorHash) { throw 'Prior bundle SHA256 mismatch.' }
if (Test-Path -LiteralPath $Destination) { throw 'Destination must be NEW.' }
& "$PSScriptRoot/source-check.ps1" -SourceZip $SourceZip -SourceSha256 $SourceSha256
$scratch = Join-Path ([IO.Path]::GetTempPath()) ('ternfold-repack-' + [guid]::NewGuid())
try {
    # Extraction is permitted only after the exact historical ZIP hash matched.
    Expand-Archive -LiteralPath $PriorBundle -DestinationPath "$scratch/prior"
    $old = "$scratch/prior"
    if ((Get-FileHash -LiteralPath "$old/source-original.zip").Hash -ine $priorSourceHash) { throw 'Prior embedded source mismatch.' }
    Expand-Archive -LiteralPath "$old/source-original.zip" -DestinationPath "$scratch/original"
    $oldFiles = @(Get-ChildItem "$old/source" -Recurse -File -Force)
    $originalFiles = @(Get-ChildItem "$scratch/original" -Recurse -File -Force)
    if ($oldFiles.Count -ne $originalFiles.Count) { throw 'Prior extracted source coverage mismatch.' }
    foreach ($file in $originalFiles) {
        $relative = [IO.Path]::GetRelativePath("$scratch/original", $file.FullName)
        if ((Get-FileHash -LiteralPath $file.FullName).Hash -ne (Get-FileHash -LiteralPath (Join-Path "$old/source" $relative)).Hash) { throw "Prior source differs: $relative" }
    }
    Expand-Archive -LiteralPath $SourceZip -DestinationPath "$scratch/new"
    function Native-Inventory([string]$Root) {
        # Only production inputs determine executable reuse. Standalone audit and
        # regression tools are rebuilt by the source quality gates, not shipped bins.
        @(Get-ChildItem -LiteralPath (Join-Path $Root 'src'),(Join-Path $Root 'include') -Recurse -File -Force | Where-Object { $_.Extension -cin @('.c','.h','.inc') } | ForEach-Object {
            $relative = [IO.Path]::GetRelativePath($Root, $_.FullName).Replace('\','/')
            '{0}  {1}' -f (Get-FileHash -LiteralPath $_.FullName).Hash, $relative
        } | Sort-Object -CaseSensitive)
    }
    $before = Native-Inventory "$old/source"
    $after = Native-Inventory "$scratch/new"
    if (-not $before.Count -or ($before -join "`n") -cne ($after -join "`n")) { throw 'Native source inventory or bytes changed; binary reuse forbidden.' }
    Write-Output "PASS: all $($before.Count) production src/include .c/.h/.inc files match the accepted source bytes and paths."
    & "$PSScriptRoot/prepare.ps1" -SourceZip $SourceZip -SourceSha256 $SourceSha256 -Destination $Destination
    foreach ($name in @('bin','licenses')) { Copy-Item -LiteralPath "$old/$name" -Destination $Destination -Recurse }
    foreach ($file in Get-ChildItem "$old/bin","$old/licenses" -File -Recurse) {
        $relative = [IO.Path]::GetRelativePath($old, $file.FullName)
        if ((Get-FileHash -LiteralPath $file.FullName).Hash -ne (Get-FileHash -LiteralPath (Join-Path $Destination $relative)).Hash) { throw "Reused file changed: $relative" }
    }
    # Preserve toolchain/import evidence while removing historical runner folders
    # from human-readable records. Executables and licenses remain byte-identical.
    foreach ($record in Get-ChildItem (Join-Path $Destination 'bin') -File -Recurse -Filter '*.txt') {
        $text = [IO.File]::ReadAllText($record.FullName)
        $text = $text.Replace('/Users/runner/work/_temp/mac-payload/', '')
        [IO.File]::WriteAllText($record.FullName, $text, [Text.UTF8Encoding]::new($false))
    }
    foreach ($name in @('bin/windows-x64/ternfold-lexer.exe','bin/macos-arm64/ternfold-lexer','bin/macos-x64/ternfold-lexer','licenses/windows-x64/LLVM-LICENSE.txt')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Destination $name) -PathType Leaf)) { throw "Missing reused file: $name" }
    }
    & "$PSScriptRoot/manifest.ps1" -Root $Destination
    Write-Output 'PASS: accepted binaries and licenses copied unchanged; build records use relative paths; new documentation and embedded source hash manifested. Native fresh-extraction gates remain required.'
} finally {
    # Only the independently allocated temporary directory is removed.
    if (Test-Path -LiteralPath $scratch) {
        $resolved = (Resolve-Path -LiteralPath $scratch).Path
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
        if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
            [IO.Path]::GetFileName($resolved) -cnotmatch '^ternfold-repack-[a-f0-9-]{36}$') { throw 'Unsafe temporary cleanup path.' }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

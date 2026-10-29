param(
    [Parameter(Mandatory=$true)][string]$SourceZip,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$SourceSha256,
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'source-check.ps1') -SourceZip $SourceZip -SourceSha256 $SourceSha256
if (Test-Path -LiteralPath $Destination) { throw 'Destination must be NEW.' }
New-Item -ItemType Directory -Path $Destination | Out-Null
Copy-Item -LiteralPath $SourceZip -Destination (Join-Path $Destination 'source-original.zip')
Expand-Archive -LiteralPath $SourceZip -DestinationPath (Join-Path $Destination 'source')
& (Join-Path $PSScriptRoot 'source-check.ps1') -SourceZip $SourceZip -SourceSha256 $SourceSha256 -SourceRoot (Join-Path $Destination 'source')
foreach ($name in @('Run-Windows.cmd','Run-Mac.command','RUN_OR_COMPILE.md')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $Destination
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'RUN_OR_COMPILE.md') -Destination (Join-Path $Destination 'README.md')
$readme = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'RUN_OR_COMPILE.md'))
[IO.File]::WriteAllText((Join-Path $Destination 'README.md'), $readme + "`nEmbedded source ZIP SHA-256: ``$($SourceSha256.ToLowerInvariant())``.`n", [Text.UTF8Encoding]::new($false))

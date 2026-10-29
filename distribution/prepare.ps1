param(
    [Parameter(Mandatory=$true)][string]$SourceZip,
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
$expected = '80b235c86b67f5b07fdc0c65c832e161eda59639ef50093e9e202a215ba2da2a'
if ((Get-FileHash -LiteralPath $SourceZip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
    throw 'Expected the immutable official IDE Source ZIP.'
}
if (Test-Path -LiteralPath $Destination) { throw 'Destination must be NEW.' }
New-Item -ItemType Directory -Path $Destination | Out-Null
Copy-Item -LiteralPath $SourceZip -Destination (Join-Path $Destination 'source-original.zip')
Expand-Archive -LiteralPath $SourceZip -DestinationPath (Join-Path $Destination 'source')
foreach ($name in @('Run-Windows.cmd','Run-Mac.command','RUN_OR_COMPILE.md')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $Destination
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'RUN_OR_COMPILE.md') -Destination (Join-Path $Destination 'README.md')

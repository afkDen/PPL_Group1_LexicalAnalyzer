param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference = 'Stop'
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$manifest = Join-Path $rootPath 'SHA256SUMS'
if (Test-Path -LiteralPath $manifest) { throw 'Manifest already exists; never overwrite a prepared payload.' }
$rows = @(Get-ChildItem -LiteralPath $rootPath -File -Recurse | ForEach-Object {
    $relative = $_.FullName.Substring($rootPath.Length + 1).Replace('\','/')
    '{0}  {1}' -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant(), $relative
} | Sort-Object)
[IO.File]::WriteAllText($manifest, ($rows -join "`n") + "`n", [Text.UTF8Encoding]::new($false))

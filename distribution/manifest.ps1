param([Parameter(Mandatory=$true)][string]$Root, [switch]$ValidateOnly)
$ErrorActionPreference = 'Stop'
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$sourceFiles = @(Get-Content -LiteralPath (Join-Path $PSScriptRoot '../SOURCE_FILES.txt') | ForEach-Object { 'source/' + $_ })
$rootFiles = @('source-original.zip','Run-Windows.cmd','Run-Mac.command','RUN_OR_COMPILE.md','README.md','SHA256SUMS')
foreach ($item in Get-ChildItem -LiteralPath $rootPath -Recurse -Force) {
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Payload links are forbidden.' }
    if ($item.PSIsContainer) { continue }
    $relative = $item.FullName.Substring($rootPath.Length + 1).Replace('\','/')
    if ($relative -cnotin $sourceFiles -and $relative -cnotin $rootFiles -and
        $relative -cnotmatch '^bin/(windows-x64/(ternfold-lexer\.exe|BUILD_INFO\.txt)|macos-(arm64|x64)/(ternfold-lexer|BUILD_INFO\.txt|imports\.txt))$' -and
        $relative -cnotmatch '^licenses/windows-x64/(LLVM-LICENSE\.txt|COPYING|COPYING\.MinGW-w64\.txt|COPYING\.MinGW-w64-runtime\.txt|COPYING\.winpthreads\.txt|COPYING\.winstorecompat\.txt)$') { throw "Unexpected payload file: $relative" }
}
if ($ValidateOnly) { return }
$manifest = Join-Path $rootPath 'SHA256SUMS'
if (Test-Path -LiteralPath $manifest) { throw 'Manifest already exists; never overwrite a prepared payload.' }
$rows = @(Get-ChildItem -LiteralPath $rootPath -File -Recurse -Force | ForEach-Object {
    $relative = $_.FullName.Substring($rootPath.Length + 1).Replace('\','/')
    '{0}  {1}' -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant(), $relative
} | Sort-Object)
[IO.File]::WriteAllText($manifest, ($rows -join "`n") + "`n", [Text.UTF8Encoding]::new($false))

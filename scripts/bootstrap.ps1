param([switch]$Offline)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
foreach ($name in @('clang','gcc','cc')) {
    if (Get-Command $name -ErrorAction SilentlyContinue) {
        & (Join-Path $PSScriptRoot 'build.ps1') environment
        exit $LASTEXITCODE
    }
}
$cache = Join-Path $projectRoot '.uv-cache/native-toolchains'
$compiler = Join-Path $cache 'llvm-mingw-20261020-ucrt-x86_64/bin/clang.exe'
if (-not (Test-Path -LiteralPath $compiler)) {
    if ($Offline) { throw 'No installed/cached compiler; install C17 Clang/GCC first.' }
    New-Item -ItemType Directory -Path $cache -Force | Out-Null
    $archive = Join-Path $cache 'llvm-mingw-20261020-ucrt-x86_64.zip'
    $expected = 'fd5462b7f5d93b2ff981fcd3f9c7e427e47f3203c64ea91c27bcc444eebd74cd'
    if (-not (Test-Path -LiteralPath $archive)) {
        Invoke-WebRequest -Uri 'https://github.com/mstorsjo/llvm-mingw/releases/download/20261020/llvm-mingw-20261020-ucrt-x86_64.zip' -OutFile $archive
    }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
        throw 'Compiler archive SHA256 mismatch; no extraction performed.'
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $cache -Force
}
& (Join-Path $PSScriptRoot 'build.ps1') environment -Compiler $compiler
exit $LASTEXITCODE

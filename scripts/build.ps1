param(
    [ValidateSet('environment','env','build','test','audit','check','sanitize','release')]
    [string]$Command = 'check',
    [string]$Compiler = $env:CC
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (-not $Compiler) {
        foreach ($candidate in @('clang','gcc','cc')) {
            $found = Get-Command $candidate -ErrorAction SilentlyContinue
            if ($found) { $Compiler = $found.Source; break }
        }
    }
    if (-not $Compiler) {
        $cachedCompiler = Join-Path $projectRoot '.uv-cache/native-toolchains/llvm-mingw-20261020-ucrt-x86_64/bin/clang.exe'
        if (Test-Path -LiteralPath $cachedCompiler) { $Compiler = $cachedCompiler }
    }
    if (-not $Compiler) { throw 'Install GCC/Clang or pass -Compiler PATH. No download is required if a supported compiler is installed.' }
    $resolvedCompiler = (Get-Command $Compiler -ErrorAction Stop).Source
    $env:TF_CC = $resolvedCompiler
    $env:PATH = (Split-Path -Parent $resolvedCompiler) + [IO.Path]::PathSeparator + $env:PATH
    New-Item -ItemType Directory -Path build -Force | Out-Null
    & $resolvedCompiler -std=c17 -Wall -Wextra -Werror -pedantic -Wconversion -Wshadow tools/tfdev.c -o build/tfdev.exe
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & (Join-Path $projectRoot 'build/tfdev.exe') $Command
    exit $LASTEXITCODE
} finally { Pop-Location }

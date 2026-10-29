param(
    [Parameter(Mandatory=$true)][string]$SourceZip,
    [Parameter(Mandatory=$true)][string]$Compiler,
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'prepare.ps1') -SourceZip $SourceZip -Destination $Destination
$rootPath = (Resolve-Path -LiteralPath $Destination).Path
$cc = (Get-Command $Compiler -ErrorAction Stop).Source
$toolchain = Split-Path -Parent (Split-Path -Parent $cc)
$version = (& $cc --version | Out-String)
if ($LASTEXITCODE -ne 0 -or $version -notmatch 'clang version 23\.1\.4' -or $version -notmatch 'x86_64-w64-windows-gnu') {
    throw 'This payload requires the verified LLVM-MinGW Clang 23.1.4 x64 toolchain.'
}
$bin = Join-Path $rootPath 'bin/windows-x64'
$licenses = Join-Path $rootPath 'licenses/windows-x64'
New-Item -ItemType Directory -Path $bin,$licenses | Out-Null
Push-Location (Join-Path $rootPath 'source')
try {
    & $cc -std=c17 -O2 -Wall -Wextra -Werror -pedantic -Wconversion -Wshadow -static -Iinclude src/main.c src/lexer.c src/source.c src/report.c -o (Join-Path $bin 'ternfold-lexer.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Native compilation failed.' }
} finally { Pop-Location }
$inspector = Join-Path (Split-Path -Parent $cc) 'llvm-readobj.exe'
$imports = (& $inspector --file-headers --coff-imports (Join-Path $bin 'ternfold-lexer.exe') | Out-String)
if ($LASTEXITCODE -ne 0 -or $imports -notmatch 'IMAGE_FILE_MACHINE_AMD64') { throw 'Not an x64 PE.' }
$dlls = @([regex]::Matches($imports, '(?m)^\s+Name: (\S+\.dll)\s*$') | ForEach-Object { $_.Groups[1].Value })
if (-not $dlls.Count) { throw 'No imports found; inspection failed.' }
foreach ($dll in $dlls) {
    if ($dll -notmatch '^(?i:KERNEL32\.dll|ADVAPI32\.dll|SHELL32\.dll|USER32\.dll|api-ms-win-crt-[a-z0-9-]+\.dll|ucrtbase\.dll)$') {
        throw "Unexpected non-system dependency: $dll. Review and bundle its redistributable license before proceeding."
    }
}
$version = $version.Replace($toolchain.Replace('\','/'), '<toolchain>').Replace($toolchain, '<toolchain>')
$imports = $imports.Replace((Join-Path $bin 'ternfold-lexer.exe'), 'bin/windows-x64/ternfold-lexer.exe')
[IO.File]::WriteAllText((Join-Path $bin 'BUILD_INFO.txt'), "Compiler:`n$version`nFlags: -std=c17 -O2 -static -Wall -Wextra -Werror -pedantic -Wconversion -Wshadow`n$imports")
Copy-Item -LiteralPath (Join-Path $toolchain 'LICENSE.TXT') -Destination (Join-Path $licenses 'LLVM-LICENSE.txt')
foreach ($name in @('COPYING','COPYING.MinGW-w64.txt','COPYING.MinGW-w64-runtime.txt','COPYING.winpthreads.txt','COPYING.winstorecompat.txt')) {
    Copy-Item -LiteralPath (Join-Path $toolchain "x86_64-w64-mingw32/share/mingw32/$name") -Destination $licenses
}
& (Join-Path $PSScriptRoot 'manifest.ps1') -Root $rootPath
Write-Output "Prepared Windows payload: $rootPath"

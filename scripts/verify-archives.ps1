param([string]$ArchiveDirectory = '', [string]$Compiler = $env:CC)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $ArchiveDirectory) { $ArchiveDirectory = Join-Path $projectRoot 'output' }
$manifest = Get-Content -Raw -LiteralPath (Join-Path $ArchiveDirectory 'archive-manifest.json') | ConvertFrom-Json
if ($manifest.schema -ne 1) { throw 'Unknown archive manifest schema' }
if (-not $Compiler) {
    foreach ($name in @('clang','gcc','cc')) {
        $found = Get-Command $name -ErrorAction SilentlyContinue
        if ($found) { $Compiler = $found.Source; break }
    }
}
if (-not $Compiler) { $Compiler = Join-Path $projectRoot '.uv-cache/native-toolchains/llvm-mingw-20261020-ucrt-x86_64/bin/clang.exe' }
$Compiler = (Get-Command $Compiler -ErrorAction Stop).Source
$pwsh = (Get-Process -Id $PID).Path
$work = Join-Path ([IO.Path]::GetTempPath()) ('Ternfold C17 clean ' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
foreach ($name in @('Ternfold_C_Lexical_Analyzer_Submission.zip','Ternfold_C17_Foundation_Final.zip')) {
    $record = @($manifest.artifacts | Where-Object { $_.name -eq $name })
    if ($record.Count -ne 1) { throw 'Archive manifest identity mismatch' }
    $record = $record[0]
    if ((Get-FileHash -LiteralPath (Join-Path $ArchiveDirectory $name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $record.sha256) { throw 'Archive SHA256 mismatch' }
    $archive = [IO.Compression.ZipFile]::OpenRead((Join-Path $ArchiveDirectory $name))
    $destination = Join-Path $work ([IO.Path]::GetFileNameWithoutExtension($name))
    New-Item -ItemType Directory -Path $destination | Out-Null
    try {
        if ($archive.Entries.Count -ne $record.entries.Count) { throw 'Archive entry count mismatch' }
        foreach ($entry in $archive.Entries) {
            $expectedEntry = @($record.entries | Where-Object { $_.path -ceq $entry.FullName })
            if ($expectedEntry.Count -ne 1) { throw 'Archive entry identity mismatch' }
            $target = [IO.Path]::GetFullPath((Join-Path $destination $entry.FullName))
            if (-not $target.StartsWith($destination + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe ZIP entry path' }
            if ($entry.FullName -match '(^|/)(\.git|\.venv|\.uv-cache|__pycache__|[^/]*\.egg-info|output|tmp)(/|$)' -or
                [IO.Path]::GetExtension($entry.FullName) -in @('.py','.pyc','.exe','.dll','.zip')) { throw ('Unexpected ZIP entry: ' + $entry.FullName) }
            New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($target)) -Force | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $false)
            if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedEntry[0].sha256) { throw ('Extracted SHA256 mismatch: ' + $entry.FullName) }
        }
    } finally { $archive.Dispose() }
    & $pwsh -NoProfile -File (Join-Path $destination 'scripts/build.ps1') environment -Compiler $Compiler
    if ($LASTEXITCODE -ne 0) { throw "Extracted environment failed: $name" }
    & $pwsh -NoProfile -File (Join-Path $destination 'scripts/build.ps1') check -Compiler $Compiler
    if ($LASTEXITCODE -ne 0) { throw "Extracted tests failed: $name" }
    Push-Location $destination
    try {
        & './build/ternfold-lexer.exe' examples/lexical/complete.tfd --output-dir build
        if ($LASTEXITCODE -ne 0) { throw 'Extracted sample failed' }
        $actual = (Get-FileHash -LiteralPath 'build/Symbol Table.txt' -Algorithm SHA256).Hash
        $expected = (Get-FileHash -LiteralPath 'tests/fixtures/lexer/Symbol Table.txt' -Algorithm SHA256).Hash
        if ($actual -ne $expected) { throw 'Fresh report differs from expected bytes' }
    } finally { Pop-Location }
    Write-Output "PASS clean extraction: $name at $destination"
}
Write-Output ('Preserved verification directories: ' + $work)

param(
    [Parameter(Mandatory=$true)][string]$Zip,
    [Parameter(Mandatory=$true)][string]$Destination,
    [switch]$Combined
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Destination) { throw 'Fresh extraction requires a NEW destination.' }
Expand-Archive -LiteralPath $Zip -DestinationPath $Destination
$rootPath = (Resolve-Path -LiteralPath $Destination).Path
$rows = @(Get-Content -LiteralPath (Join-Path $rootPath 'SHA256SUMS'))
$files = @(Get-ChildItem -LiteralPath $rootPath -Recurse -File)
if ($files.Count -ne $rows.Count + 1) { throw 'Manifest coverage differs from payload.' }
$seen = @{}
foreach ($row in $rows) {
    if ($row -notmatch '^([a-f0-9]{64})  ([^\r\n]+)$') { throw 'Malformed manifest entry.' }
    $digest = $Matches[1]; $relative = $Matches[2]
    if ($relative -eq 'SHA256SUMS' -or $seen.ContainsKey($relative)) { throw 'Manifest duplicate/self-reference.' }
    $seen[$relative] = $true
    $path = [IO.Path]::GetFullPath((Join-Path $rootPath $relative))
    if (-not $path.StartsWith($rootPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Escaping path.' }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $digest) { throw "Hash mismatch: $relative" }
}
$original = Join-Path $rootPath 'source-original.zip'
if ((Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash.ToLowerInvariant() -ne '80b235c86b67f5b07fdc0c65c832e161eda59639ef50093e9e202a215ba2da2a') { throw 'Official source changed.' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($original)
try {
    $entries = @($archive.Entries | Where-Object { -not $_.FullName.EndsWith('/') })
    if ($entries.Count -ne 33 -or @(Get-ChildItem -LiteralPath (Join-Path $rootPath 'source') -Recurse -File).Count -ne 33) { throw 'Source allowlist changed.' }
    foreach ($entry in $entries) {
        $stream = $entry.Open(); $sha = [Security.Cryptography.SHA256]::Create()
        try { $expected = ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
        finally { $stream.Dispose(); $sha.Dispose() }
        if ((Get-FileHash -LiteralPath (Join-Path $rootPath ('source/' + $entry.FullName)) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw "Source changed: $($entry.FullName)" }
    }
} finally { $archive.Dispose() }
if ($Combined) {
    foreach ($target in @('macos-arm64','macos-x64')) {
        if (-not (Test-Path -LiteralPath (Join-Path $rootPath "bin/$target/ternfold-lexer"))) { throw "Missing $target binary." }
    }
}
$savedPath = $env:PATH
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
Push-Location $rootPath
function Expect-Exit([int]$Actual, [int]$Expected, [string]$Label) {
    if ($Actual -ne $Expected) { throw "$Label exit $Actual; expected $Expected" }
}
function Equal-File([string]$Left, [string]$Right) {
    if ((Get-FileHash -LiteralPath $Left).Hash -ne (Get-FileHash -LiteralPath $Right).Hash) { throw "Different files: $Left / $Right" }
}
try {
    Write-Output "Clean PATH: $env:PATH"
    # Exercise the actual double-click/default route, including pause, with an
    # injected Return. The shell command is constant; paths use WorkingDirectory.
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = Join-Path $env:SystemRoot 'System32/cmd.exe'
    $start.Arguments = '/d /c Run-Windows.cmd'
    $start.WorkingDirectory = $rootPath
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardInput = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    try {
        if (-not $process.Start()) { throw 'Default launcher did not start.' }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $process.StandardInput.WriteLine()
        $process.StandardInput.Close()
        if (-not $process.WaitForExit(30000)) { $process.Kill(); throw 'Default launcher pause timed out.' }
        $defaultOutput = $stdout.GetAwaiter().GetResult()
        Write-Output $defaultOutput
        if ($process.ExitCode -ne 0 -or $defaultOutput -notmatch 'Symbol Table.txt written') { throw 'Default launcher failed.' }
        if ($stderr.GetAwaiter().GetResult()) { throw 'Unexpected default launcher diagnostic.' }
    } finally { $process.Dispose() }
    Equal-File 'reports/Symbol Table.txt' 'source/tests/fixtures/lexer/Classroom Symbol Table.txt'
    & ./Run-Windows.cmd --demo
    Expect-Exit $LASTEXITCODE 0 'Launcher complete demo'
    Equal-File 'reports/Symbol Table.txt' 'source/tests/fixtures/lexer/Classroom Symbol Table.txt'
    & ./Run-Windows.cmd source/examples/lexical/invalid.tfd
    Expect-Exit $LASTEXITCODE 1 'Launcher invalid demo'
    Equal-File 'reports/Symbol Table.txt' 'source/tests/fixtures/lexer/Invalid Classroom Symbol Table.txt'
    $before = (Get-FileHash -LiteralPath 'reports/Symbol Table.txt').Hash
    & ./Run-Windows.cmd missing-do-not-open.txt 2> extension.txt
    Expect-Exit $LASTEXITCODE 1 'Extension rejection'
    if ((Get-Content extension.txt -Raw) -notmatch 'extension must be exactly .tfd') { throw 'Wrong extension diagnostic.' }
    if ((Get-FileHash -LiteralPath 'reports/Symbol Table.txt').Hash -ne $before) { throw 'Extension fault changed report.' }
    & ./bin/windows-x64/ternfold-lexer.exe 2> usage.txt
    Expect-Exit $LASTEXITCODE 2 'No-argument usage'
    Copy-Item -LiteralPath 'source/examples/lexical/complete.tfd' -Destination 'path with spaces.tfd'
    & ./Run-Windows.cmd 'path with spaces.tfd'
    Expect-Exit $LASTEXITCODE 0 'Launcher input with spaces'
    Equal-File 'reports/Symbol Table.txt' 'source/tests/fixtures/lexer/Classroom Symbol Table.txt'
    $launcher = Join-Path $rootPath 'Run-Windows.cmd'
    $inputPath = Join-Path $rootPath 'path with spaces.tfd'
    Push-Location (Join-Path $rootPath 'source/examples')
    try {
        & $launcher $inputPath
        Expect-Exit $LASTEXITCODE 0 'Launcher from another working directory'
    } finally { Pop-Location }
    Equal-File 'reports/Symbol Table.txt' 'source/tests/fixtures/lexer/Classroom Symbol Table.txt'
    Write-Output 'PASS: fresh ZIP, all hashes, 33 unchanged source files, valid/invalid/extension/usage/spaces/non-root CWD/default pause; system-only PATH.'
} finally { Pop-Location; $env:PATH = $savedPath }

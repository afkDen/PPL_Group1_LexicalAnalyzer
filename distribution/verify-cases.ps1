param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference = 'Stop'
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$exe = Join-Path $rootPath 'bin/windows-x64/ternfold-lexer.exe'
$output = Join-Path $rootPath 'oracle-output'
New-Item -ItemType Directory -Path $output | Out-Null
foreach ($case in @('complete','vocabulary','invalid-comprehensive','trace')) {
    foreach ($mode in @('classroom','lossless','trace')) {
        $start = [Diagnostics.ProcessStartInfo]::new($exe)
        $start.WorkingDirectory = Join-Path $rootPath 'source'
        $start.UseShellExecute = $false
        $start.RedirectStandardOutput = $true
        $start.RedirectStandardError = $true
        foreach ($arg in @("examples/lexical/$case.tfd",'--output-dir',$output)) { $start.ArgumentList.Add($arg) }
        if ($mode -ne 'lossless') { $start.ArgumentList.Add('--classroom') }
        if ($mode -eq 'trace') { $start.ArgumentList.Add('--trace-dfa') }
        $process = [Diagnostics.Process]::new(); $process.StartInfo = $start
        try {
            if (-not $process.Start()) { throw 'Case process did not start.' }
            $stdout = $process.StandardOutput.ReadToEndAsync(); $stderr = $process.StandardError.ReadToEndAsync()
            if (-not $process.WaitForExit(30000)) { $process.Kill(); throw 'Case timed out.' }
            $null = $stdout.GetAwaiter().GetResult(); $diagnostics = $stderr.GetAwaiter().GetResult()
            $expectedExit = if ($case -in @('complete','vocabulary')) { 0 } else { 1 }
            if ($process.ExitCode -ne $expectedExit) { throw "$case/$mode wrong exit: $($process.ExitCode)" }
        } finally { $process.Dispose() }
        $fixtureMode = if ($mode -eq 'lossless') { 'lossless' } else { 'classroom' }
        $fixture = Join-Path $rootPath "source/tests/fixtures/invalid/$case.$fixtureMode.txt"
        if ((Get-FileHash $fixture).Hash -ne (Get-FileHash (Join-Path $output 'Symbol Table.txt')).Hash) { throw "$case/$mode report differs." }
        if ($mode -eq 'trace') {
            if ($diagnostics -notmatch '(?m)^DFA \w+ offset=\d+ end=\d+ state=' -or $diagnostics -notmatch ' FINAL \[') { throw 'Missing actual DFA transitions/finals.' }
            $diagnostics = [regex]::Replace($diagnostics, '(?m)^DFA [^\r\n]*\r?\n', '')
        }
        $expected = [IO.File]::ReadAllText((Join-Path $rootPath "source/tests/fixtures/invalid/$case.diagnostics.txt"))
        if ($diagnostics -cne $expected) { throw "$case/$mode diagnostics/spans differ." }
    }
}
Write-Output 'PASS: 12 packaged-binary cases, exact reports/diagnostics/spans and actual trace transitions.'

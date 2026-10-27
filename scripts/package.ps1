param([string]$OutputDirectory = '')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $projectRoot 'output' }
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$script:artifactRecords = @()

function Add-Tree($Map, $Directory) {
    $base = Join-Path $projectRoot $Directory
    foreach ($file in Get-ChildItem -LiteralPath $base -Recurse -File) {
        $relative = $file.FullName.Substring($projectRoot.Length + 1).Replace('\','/')
        if ($relative -match '(^|/)(__pycache__|[^/]*\.egg-info|\.venv|\.uv-cache|build|output|tmp)(/|$)' -or
            $file.Extension -in @('.py','.pyc','.exe','.dll','.o','.obj','.zip')) { continue }
        $Map[$relative] = $file.FullName
    }
}
function Write-Zip($Name, $Map) {
    $destination = Join-Path $OutputDirectory $Name
    $entries = @()
    $stream = [IO.File]::Open($destination, [IO.FileMode]::Create, [IO.FileAccess]::ReadWrite)
    $zip = [IO.Compression.ZipArchive]::new($stream, [IO.Compression.ZipArchiveMode]::Create, $false)
    try {
        foreach ($relative in ($Map.Keys | Sort-Object)) {
            $entry = $zip.CreateEntry($relative, [IO.Compression.CompressionLevel]::Optimal)
            $entry.LastWriteTime = [DateTimeOffset]::new(2026,10,28,0,0,0,[TimeSpan]::Zero)
            $out = $entry.Open()
            $inputStream = [IO.File]::OpenRead($Map[$relative])
            try { $inputStream.CopyTo($out) } finally { $inputStream.Dispose(); $out.Dispose() }
            $entries += [ordered]@{path=$relative; sha256=(Get-FileHash -LiteralPath $Map[$relative] -Algorithm SHA256).Hash.ToLowerInvariant()}
        }
    } finally { $zip.Dispose(); $stream.Dispose() }
    $file = Get-Item -LiteralPath $destination
    $script:artifactRecords += [ordered]@{name=$Name; bytes=$file.Length;
        sha256=(Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant(); entries=$entries}
    Write-Output ($file.Name + ': ' + $Map.Count + ' files, ' + $file.Length + ' bytes, SHA256 ' +
        (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant())
}
$full = @{}
foreach ($dir in @('include','src','tests','tools','scripts','examples','docs','.codex','.agents','submission')) {
    Add-Tree $full $dir
}
foreach ($file in @('README.md','MASTER_IMPLEMENTATION.md','AGENTS.md','.gitignore','.gitattributes','build.bat')) {
    $full[$file] = Join-Path $projectRoot $file
}
$lexical = @{}
foreach ($dir in @('include','src','tests','tools','examples/lexical')) { Add-Tree $lexical $dir }
foreach ($file in @('scripts/build.ps1','scripts/build.sh','build.bat')) { $lexical[$file] = Join-Path $projectRoot $file }
$lexical['README.md'] = Join-Path $projectRoot 'submission/lexical/README.md'
$lexical['LEXICAL_PACKAGE'] = Join-Path $projectRoot 'submission/lexical/LEXICAL_PACKAGE'
Write-Zip 'Ternfold_C_Lexical_Analyzer_Submission.zip' $lexical
Write-Zip 'Ternfold_C17_Foundation_Final.zip' $full
[ordered]@{schema=1; artifacts=$script:artifactRecords} | ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath (Join-Path $OutputDirectory 'archive-manifest.json') -Encoding UTF8

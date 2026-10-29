param(
    [Parameter(Mandatory=$true)][string]$SourceZipUrl,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$SourceSha256
)
$ErrorActionPreference = 'Stop'
if ($SourceZipUrl -cnotmatch '^https://github\.com/afkDen/PPL_Group1_LexicalAnalyzer/releases/download/[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*\.zip$') {
    throw 'Expected an explicit ZIP release URL in afkDen/PPL_Group1_LexicalAnalyzer.'
}

<#
.SYNOPSIS
把项目根目录下的 nltk_data 打包成 GitHub Release 附件。

.DESCRIPTION
脚本会检查根目录下的 nltk_data 是否存在，然后把它压缩成 zip，
输出到 dist/releases 目录，并额外生成：

- 同名 .sha256 校验文件
- 同名 .txt 发布说明

默认会带上时间戳，避免覆盖旧包。

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\package-nltk-data-release.ps1

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\package-nltk-data-release.ps1 -Version v1
#>
[CmdletBinding()]
param(
    [string]$Version,
    [switch]$OverwriteLatest
)

$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
    $scriptDir = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $scriptDir '..')).Path
}

function Ensure-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Get-DirectorySizeBytes {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $measure = Get-ChildItem -LiteralPath $Path -Recurse -File | Measure-Object -Property Length -Sum
    return [int64]($measure.Sum)
}

function Format-SizeMB {
    param(
        [Parameter(Mandatory = $true)]
        [int64]$Bytes
    )

    return '{0:N2} MB' -f ($Bytes / 1MB)
}

$repoRoot = Get-RepoRoot
$nltkDataDir = Join-Path $repoRoot 'nltk_data'
$releaseDir = Join-Path $repoRoot 'dist\releases'

if (-not (Test-Path -LiteralPath $nltkDataDir)) {
    throw "Missing nltk_data directory: $nltkDataDir"
}

Ensure-Directory -Path $releaseDir

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$versionPart = if ([string]::IsNullOrWhiteSpace($Version)) { $timestamp } else { $Version.Trim() }
$baseName = "nltk_data-release-$versionPart"
$zipPath = Join-Path $releaseDir "$baseName.zip"
$shaPath = Join-Path $releaseDir "$baseName.sha256"
$notePath = Join-Path $releaseDir "$baseName.txt"

if ($OverwriteLatest) {
    $zipPath = Join-Path $releaseDir 'nltk_data-release-latest.zip'
    $shaPath = Join-Path $releaseDir 'nltk_data-release-latest.sha256'
    $notePath = Join-Path $releaseDir 'nltk_data-release-latest.txt'
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
if (Test-Path -LiteralPath $shaPath) {
    Remove-Item -LiteralPath $shaPath -Force
}
if (Test-Path -LiteralPath $notePath) {
    Remove-Item -LiteralPath $notePath -Force
}

Write-Host "Packaging nltk_data from: $nltkDataDir"
Write-Host "Output zip: $zipPath"

Compress-Archive -LiteralPath $nltkDataDir -DestinationPath $zipPath -CompressionLevel Optimal

$hash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
$sourceSizeBytes = Get-DirectorySizeBytes -Path $nltkDataDir
$zipSizeBytes = (Get-Item -LiteralPath $zipPath).Length

@(
    "$($hash.Hash) *$(Split-Path -Leaf $zipPath)"
) | Set-Content -LiteralPath $shaPath -Encoding utf8

$noteLines = @(
    'NLTK data release attachment',
    '',
    "Generated at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "Source directory: nltk_data/",
    "Source size: $(Format-SizeMB -Bytes $sourceSizeBytes)",
    "Zip size: $(Format-SizeMB -Bytes $zipSizeBytes)",
    "SHA256: $($hash.Hash)",
    '',
    'How to use:',
    '1. Download the zip release asset.',
    '2. Extract it into the repository root.',
    '3. Make sure the final path is <repo>/nltk_data/',
    '4. Start Open WebUI normally.',
    '',
    'Note:',
    '- Do not leave it as a zip only; extract it before running.',
    '- The repo already points NLTK_DATA at the root nltk_data directory.'
)
$noteLines | Set-Content -LiteralPath $notePath -Encoding utf8

Write-Host ''
Write-Host 'Package summary'
Write-Host "  Source size: $(Format-SizeMB -Bytes $sourceSizeBytes)"
Write-Host "  Zip size:    $(Format-SizeMB -Bytes $zipSizeBytes)"
Write-Host "  SHA256 file: $shaPath"
Write-Host "  Note file:   $notePath"

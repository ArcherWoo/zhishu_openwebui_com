<#
.SYNOPSIS
把 Pyodide 内网离线运行时资源打包成 GitHub Release 附件。
.DESCRIPTION
这个脚本会把仓库里的两部分资源一起打包：
- vendor/npm/        前端 npm 离线缓存
- static/pyodide/    Pyodide 浏览器运行时与离线 wheel

之所以两部分要一起带走，是因为公司内网里真正先失败的是 npm 构建期；
如果只有 static/pyodide 而没有 vendor/npm，npm ci 依然可能先失败。

输出位置：
- dist/releases/*.zip
- dist/releases/*.sha256
- dist/releases/*.txt

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\package-pyodide-release.ps1

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\package-pyodide-release.ps1 -Version v1

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\package-pyodide-release.ps1 -OverwriteLatest
#>
[CmdletBinding()]
param(
    [string]$Version,
    [switch]$OverwriteLatest
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

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

    if (-not (Test-Path -LiteralPath $Path)) {
        return [int64]0
    }

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

function Add-DirectoryToZip {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.Compression.ZipArchive]$Archive,
        [Parameter(Mandatory = $true)]
        [string]$SourcePath,
        [Parameter(Mandatory = $true)]
        [string]$EntryRoot
    )

    $files = Get-ChildItem -LiteralPath $SourcePath -Recurse -File
    foreach ($file in $files) {
        $relativePath = $file.FullName.Substring($SourcePath.Length).TrimStart('\', '/')
        $entryName = if ([string]::IsNullOrWhiteSpace($relativePath)) {
            ($EntryRoot -replace '\\', '/')
        } else {
            (($EntryRoot.TrimEnd('\', '/')) + '/' + ($relativePath -replace '\\', '/'))
        }

        $entry = $Archive.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
        $entryStream = $entry.Open()
        $fileStream = [System.IO.File]::OpenRead($file.FullName)
        try {
            $fileStream.CopyTo($entryStream)
        } finally {
            $fileStream.Dispose()
            $entryStream.Dispose()
        }
    }
}

$repoRoot = Get-RepoRoot
$npmCacheDir = Join-Path $repoRoot 'vendor\npm'
$pyodideDir = Join-Path $repoRoot 'static\pyodide'
$releaseDir = Join-Path $repoRoot 'dist\releases'

if (-not (Test-Path -LiteralPath $npmCacheDir)) {
    throw "Missing npm cache directory: $npmCacheDir"
}

if (-not (Test-Path -LiteralPath $pyodideDir)) {
    throw "Missing Pyodide runtime directory: $pyodideDir"
}

if (-not (Test-Path -LiteralPath (Join-Path $pyodideDir 'pyodide-lock.json'))) {
    throw "Missing Pyodide lock file: $(Join-Path $pyodideDir 'pyodide-lock.json')"
}

Ensure-Directory -Path $releaseDir

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$versionPart = if ([string]::IsNullOrWhiteSpace($Version)) { $timestamp } else { $Version.Trim() }
$baseName = "pyodide-offline-runtime-$versionPart"
$zipPath = Join-Path $releaseDir "$baseName.zip"
$shaPath = Join-Path $releaseDir "$baseName.sha256"
$notePath = Join-Path $releaseDir "$baseName.txt"

if ($OverwriteLatest) {
    $zipPath = Join-Path $releaseDir 'pyodide-offline-runtime-latest.zip'
    $shaPath = Join-Path $releaseDir 'pyodide-offline-runtime-latest.sha256'
    $notePath = Join-Path $releaseDir 'pyodide-offline-runtime-latest.txt'
}

foreach ($path in @($zipPath, $shaPath, $notePath)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

Write-Host "Packaging frontend npm cache from: $npmCacheDir"
Write-Host "Packaging pyodide runtime from: $pyodideDir"
Write-Host "Output zip: $zipPath"

$zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    Add-DirectoryToZip -Archive $zip -SourcePath $npmCacheDir -EntryRoot 'vendor/npm'
    Add-DirectoryToZip -Archive $zip -SourcePath $pyodideDir -EntryRoot 'static/pyodide'
} finally {
    $zip.Dispose()
}

$hash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
$npmCacheSizeBytes = Get-DirectorySizeBytes -Path $npmCacheDir
$pyodideSizeBytes = Get-DirectorySizeBytes -Path $pyodideDir
$zipSizeBytes = (Get-Item -LiteralPath $zipPath).Length
$combinedSizeBytes = $npmCacheSizeBytes + $pyodideSizeBytes

@(
    "$($hash.Hash) *$(Split-Path -Leaf $zipPath)"
) | Set-Content -LiteralPath $shaPath -Encoding utf8

$noteLines = @(
    'Pyodide offline runtime release attachment',
    '',
    "Generated at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    'Included directories:',
    '- vendor/npm/',
    '- static/pyodide/',
    '',
    "Combined source size: $(Format-SizeMB -Bytes $combinedSizeBytes)",
    "NPM cache size:       $(Format-SizeMB -Bytes $npmCacheSizeBytes)",
    "Pyodide runtime size: $(Format-SizeMB -Bytes $pyodideSizeBytes)",
    "Zip size:             $(Format-SizeMB -Bytes $zipSizeBytes)",
    "SHA256: $($hash.Hash)",
    '',
    'How to use in intranet:',
    '1. Download the zip release asset into the repository.',
    '2. Run scripts/restore-pyodide-release.ps1 against that zip.',
    '3. Confirm vendor/npm/ and static/pyodide/ are restored.',
    '4. Start Open WebUI with python start.py.',
    '',
    'Important:',
    '- This bundle intentionally includes the full frontend npm cache, not only pyodide.',
    '- Do not commit the extracted vendor/ directory into git.',
    '- Keep the zip in GitHub Release attachments or private artifact storage.'
)
$noteLines | Set-Content -LiteralPath $notePath -Encoding utf8

Write-Host ''
Write-Host 'Package summary'
Write-Host "  Combined source size: $(Format-SizeMB -Bytes $combinedSizeBytes)"
Write-Host "  NPM cache size:       $(Format-SizeMB -Bytes $npmCacheSizeBytes)"
Write-Host "  Pyodide runtime size: $(Format-SizeMB -Bytes $pyodideSizeBytes)"
Write-Host "  Zip size:             $(Format-SizeMB -Bytes $zipSizeBytes)"
Write-Host "  SHA256 file:          $shaPath"
Write-Host "  Note file:            $notePath"

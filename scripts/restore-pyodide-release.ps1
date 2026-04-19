<#
.SYNOPSIS
把 Pyodide 离线运行时 zip 恢复回当前仓库。
.DESCRIPTION
这个脚本会把 Release 附件中的两个目录恢复到仓库标准位置：
- vendor/npm/
- static/pyodide/

适用于公司内网环境把外网打好的 zip 带回来之后，直接一键解压恢复。

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\restore-pyodide-release.ps1 -ArchivePath .\pyodide_runtime\pyodide-offline-runtime-latest.zip

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\restore-pyodide-release.ps1 -ArchivePath .\dist\releases\pyodide-offline-runtime-latest.zip
#>
[CmdletBinding()]
param(
    [string]$ArchivePath,
    [string]$DestinationRoot
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Get-RepoRoot {
    $scriptDir = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $scriptDir '..')).Path
}

function Resolve-OptionalPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (Test-Path -LiteralPath $Path) {
        return (Resolve-Path -LiteralPath $Path).Path
    }

    return $null
}

function Convert-ToLongPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if ($Path.StartsWith('\\?\')) {
        return $Path
    }

    if ($Path.StartsWith('\\')) {
        return '\\?\UNC\' + $Path.TrimStart('\')
    }

    return '\\?\' + $Path
}

$repoRoot = Get-RepoRoot
$resolvedDestinationRoot = if ([string]::IsNullOrWhiteSpace($DestinationRoot)) {
    $repoRoot
} else {
    [System.IO.Path]::GetFullPath($DestinationRoot)
}

if (-not (Test-Path -LiteralPath $resolvedDestinationRoot)) {
    throw "Destination root does not exist: $resolvedDestinationRoot"
}

if ([string]::IsNullOrWhiteSpace($ArchivePath)) {
    $candidatePaths = @(
        (Join-Path $repoRoot 'pyodide_runtime\pyodide-offline-runtime-latest.zip'),
        (Join-Path $repoRoot 'dist\releases\pyodide-offline-runtime-latest.zip')
    )
    $resolvedArchivePath = $null
    foreach ($candidate in $candidatePaths) {
        $resolved = Resolve-OptionalPath -Path $candidate
        if ($resolved) {
            $resolvedArchivePath = $resolved
            break
        }
    }
} else {
    $candidate = if ([System.IO.Path]::IsPathRooted($ArchivePath)) {
        $ArchivePath
    } else {
        Join-Path $repoRoot $ArchivePath
    }
    $resolvedArchivePath = Resolve-OptionalPath -Path $candidate
}

if (-not $resolvedArchivePath) {
    throw 'Could not find the Pyodide runtime zip. Please pass -ArchivePath explicitly.'
}

$targetNpmDir = Join-Path $resolvedDestinationRoot 'vendor\npm'
$targetPyodideDir = Join-Path $resolvedDestinationRoot 'static\pyodide'

Write-Host "Restoring Pyodide offline runtime from: $resolvedArchivePath"
Write-Host "Destination root: $resolvedDestinationRoot"

foreach ($target in @($targetNpmDir, $targetPyodideDir)) {
    if (Test-Path -LiteralPath $target) {
        Write-Host "Clearing existing target: $target"
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

$zip = [System.IO.Compression.ZipFile]::OpenRead($resolvedArchivePath)
try {
    foreach ($entry in $zip.Entries) {
        if ([string]::IsNullOrWhiteSpace($entry.Name)) {
            continue
        }

        $relativeEntryPath = $entry.FullName -replace '/', '\'
        $targetFilePath = [System.IO.Path]::GetFullPath((Join-Path $resolvedDestinationRoot $relativeEntryPath))

        if (-not $targetFilePath.StartsWith($resolvedDestinationRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Archive entry escaped destination root: $($entry.FullName)"
        }

        $targetDirectory = Split-Path -Parent $targetFilePath
        if (-not (Test-Path -LiteralPath $targetDirectory)) {
            [System.IO.Directory]::CreateDirectory((Convert-ToLongPath -Path $targetDirectory)) | Out-Null
        }

        [System.IO.Compression.ZipFileExtensions]::ExtractToFile(
            $entry,
            (Convert-ToLongPath -Path $targetFilePath),
            $true
        )
    }
} finally {
    $zip.Dispose()
}

if (-not (Test-Path -LiteralPath $targetNpmDir)) {
    throw "Restore finished but vendor/npm is missing: $targetNpmDir"
}

if (-not (Test-Path -LiteralPath (Join-Path $targetPyodideDir 'pyodide-lock.json'))) {
    throw "Restore finished but static/pyodide/pyodide-lock.json is missing: $(Join-Path $targetPyodideDir 'pyodide-lock.json')"
}

Write-Host ''
Write-Host 'Restore summary'
Write-Host "  npm cache directory:   $targetNpmDir"
Write-Host "  pyodide runtime dir:   $targetPyodideDir"
Write-Host '  next step:             python start.py'

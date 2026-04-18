<#
.SYNOPSIS
整理项目根目录里的历史日志和临时产物。

.DESCRIPTION
把根目录散落的历史日志归档到 logs/root-archive 下的分类目录里，
并尝试清理常见的根目录缓存/临时目录，例如 __pycache__、.tmp-py、.tmp-pytest。

脚本只处理仓库根目录的文件和少量明确的临时目录，不会移动源码、依赖目录、
.start-state.json 之类的运行状态文件。

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup-root-artifacts.ps1 -WhatIf

先预览将要执行的整理动作。

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup-root-artifacts.ps1

执行整理动作。
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
    $scriptDir = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $scriptDir '..')).Path
}

function Assert-InsideRepo {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $resolvedRoot = [System.IO.Path]::GetFullPath($RepoRoot)
    $resolvedPath = [System.IO.Path]::GetFullPath($Path)

    if (-not $resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to touch path outside repo: $resolvedPath"
    }
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

function Get-UniqueDestinationPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $Path
    }

    $directory = Split-Path -Parent $Path
    $leaf = Split-Path -Leaf $Path
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($leaf)
    $extension = [System.IO.Path]::GetExtension($leaf)
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $counter = 1

    do {
        $candidate = Join-Path $directory ("{0}-{1}-{2}{3}" -f $baseName, $timestamp, $counter, $extension)
        $counter++
    } while (Test-Path -LiteralPath $candidate)

    return $candidate
}

function Move-RootArtifacts {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $archiveRoot = Join-Path $RepoRoot 'logs\root-archive'
    $categories = @('build', 'debug', 'service', 'smoke', 'start', 'shutdown', 'tmp', 'verify')

    Ensure-Directory -Path $archiveRoot
    foreach ($category in $categories) {
        Ensure-Directory -Path (Join-Path $archiveRoot $category)
    }

    $rules = @(
        @{ Pattern = 'debug-*.log'; Target = 'debug' },
        @{ Pattern = 'service-install-test*.log'; Target = 'service' },
        @{ Pattern = 'smoke-start*.log'; Target = 'smoke' },
        @{ Pattern = 'start-prod-detach-test*.log'; Target = 'start' },
        @{ Pattern = 'start-prod-test*.log'; Target = 'start' },
        @{ Pattern = 'start-test*.log'; Target = 'start' },
        @{ Pattern = 'verify-*.log'; Target = 'verify' },
        @{ Pattern = 'tmp-build-warnings*.log'; Target = 'build' },
        @{ Pattern = 'tmp-shutdown-repro.log'; Target = 'shutdown' },
        @{ Pattern = 'tmp-open-webui*.log'; Target = 'tmp' }
    )

    $moved = New-Object System.Collections.Generic.List[string]

    foreach ($rule in $rules) {
        Get-ChildItem -LiteralPath $RepoRoot -File -Filter $rule.Pattern | ForEach-Object {
            $sourcePath = $_.FullName
            $targetDir = Join-Path $archiveRoot $rule.Target
            $destinationPath = Get-UniqueDestinationPath -Path (Join-Path $targetDir $_.Name)

            Assert-InsideRepo -RepoRoot $RepoRoot -Path $sourcePath
            Assert-InsideRepo -RepoRoot $RepoRoot -Path $destinationPath

            if ($PSCmdlet.ShouldProcess($sourcePath, "Move to $destinationPath")) {
                Move-Item -LiteralPath $sourcePath -Destination $destinationPath
                $moved.Add($_.Name) | Out-Null
            }
        }
    }

    return $moved
}

function Remove-TempDirectories {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $directoryNames = @(
        '__pycache__',
        '.tmp-py',
        '.tmp-pytest',
        'tmp-runtime-temp',
        'tmp-test-artifacts',
        'tmp-upload-decryption-smoke',
        '.tmp-probe-root'
    )

    $removed = New-Object System.Collections.Generic.List[string]
    $failed = New-Object System.Collections.Generic.List[string]

    foreach ($directoryName in $directoryNames) {
        $targetPath = Join-Path $RepoRoot $directoryName
        Assert-InsideRepo -RepoRoot $RepoRoot -Path $targetPath

        if (-not (Test-Path -LiteralPath $targetPath)) {
            continue
        }

        try {
            if ($PSCmdlet.ShouldProcess($targetPath, 'Remove temporary directory')) {
                Remove-Item -LiteralPath $targetPath -Recurse -Force
                $removed.Add($directoryName) | Out-Null
            }
        } catch {
            $failed.Add(('{0}: {1}' -f $directoryName, $_.Exception.Message)) | Out-Null
            Write-Warning "Failed to remove $directoryName - $($_.Exception.Message)"
        }
    }

    return @{
        Removed = $removed
        Failed = $failed
    }
}

$repoRoot = Get-RepoRoot
Set-Location -LiteralPath $repoRoot

$movedFiles = Move-RootArtifacts -RepoRoot $repoRoot
$cleanupResult = Remove-TempDirectories -RepoRoot $repoRoot

Write-Host ''
Write-Host 'Cleanup summary'
Write-Host "  Repo root: $repoRoot"
Write-Host "  Archived files: $($movedFiles.Count)"
Write-Host "  Removed temp dirs: $($cleanupResult.Removed.Count)"
Write-Host "  Failed temp dirs: $($cleanupResult.Failed.Count)"

if ($movedFiles.Count -gt 0) {
    Write-Host '  Archived file list:'
    foreach ($name in $movedFiles) {
        Write-Host "    - $name"
    }
}

if ($cleanupResult.Removed.Count -gt 0) {
    Write-Host '  Removed directories:'
    foreach ($name in $cleanupResult.Removed) {
        Write-Host "    - $name"
    }
}

if ($cleanupResult.Failed.Count -gt 0) {
    Write-Host '  Failed directories:'
    foreach ($entry in $cleanupResult.Failed) {
        Write-Host "    - $entry"
    }
}

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$packageRoot = Join-Path $root "portable_packages"
$stage = Join-Path $packageRoot "finance-radar_$stamp"
$zip = Join-Path $packageRoot "finance-radar_$stamp.zip"

New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null
New-Item -ItemType Directory -Force -Path $stage | Out-Null

$excludeDirs = @(
    ".git",
    "__pycache__",
    ".pytest_cache",
    "_recovery_snapshots",
    "portable_packages"
)

$excludeFiles = @(
    ".env",
    "*.pyc"
)

function Should-SkipPath($path, $name) {
    $relative = $path.Substring($root.Length).TrimStart('\', '/')
    $segments = $relative -split '[\\/]'
    foreach ($segment in $segments) {
        if ($excludeDirs -contains $segment) {
            return $true
        }
    }
    foreach ($pattern in $excludeFiles) {
        if ($name -like $pattern) {
            return $true
        }
    }
    return $false
}

Get-ChildItem -LiteralPath $root -Force -Recurse -File | ForEach-Object {
    if (Should-SkipPath $_.FullName $_.Name) {
        return
    }
    $relative = $_.FullName.Substring($root.Length).TrimStart('\', '/')
    $destination = Join-Path $stage $relative
    $destinationDir = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
}

Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -Force

Write-Host "Portable package created:"
Write-Host $zip
Write-Host ""
Write-Host "Note: .env is excluded by default. Create .env from .env.example on the target computer if needed."

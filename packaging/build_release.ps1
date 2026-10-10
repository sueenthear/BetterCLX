param(
    [switch]$SkipAppBuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Version = (Select-String -Path (Join-Path $ProjectRoot "pyproject.toml") -Pattern '^version\s*=\s*"([^"]+)"').Matches.Groups[1].Value
if (-not $Version) { throw "Unable to read version from pyproject.toml" }
$Tag = "v${Version}_build$(Get-Date -Format yyMMdd)"
$ReleaseRoot = Join-Path $ProjectRoot "release\$Tag"
$DistRoot = Join-Path $ReleaseRoot "dist"
$BuildRoot = Join-Path $ProjectRoot "build\$Tag"
$AppDist = Join-Path $DistRoot "BetterCLX"
$Payload = Join-Path $ProjectRoot "packaging\payload"
$Installer = Join-Path $ReleaseRoot "BetterCLX-Setup-$Tag.exe"
$AppSpec = Join-Path $ProjectRoot "packaging\BetterCLX.spec"
$SetupSpec = Join-Path $ProjectRoot "packaging\setup.spec"

New-Item -ItemType Directory -Force -Path $DistRoot,$BuildRoot | Out-Null
if (-not $SkipAppBuild -or -not (Test-Path (Join-Path $AppDist "BetterCLX.exe"))) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $AppDist,(Join-Path $BuildRoot "app")
    Write-Host "[1/4] Building BetterCLX onedir: $Tag"
    uv run pyinstaller --noconfirm --clean --distpath $DistRoot --workpath (Join-Path $BuildRoot "app") $AppSpec
    if ($LASTEXITCODE -ne 0) { throw "BetterCLX onedir build failed" }
} else {
    Write-Host "[1/4] Reusing BetterCLX onedir: $AppDist"
}

Write-Host "[2/4] Preparing installer payload"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Payload
New-Item -ItemType Directory -Force -Path $Payload | Out-Null
Copy-Item -Recurse -Force (Join-Path $AppDist "*") $Payload
New-Item -ItemType Directory -Force -Path (Join-Path $Payload "examples\combo") | Out-Null
Copy-Item -Force (Join-Path $ProjectRoot "combo\*.json") (Join-Path $Payload "examples\combo")

Write-Host "[3/4] Building Tk self-extracting installer"
Remove-Item -Force -ErrorAction SilentlyContinue $Installer
uv run pyinstaller --noconfirm --clean --distpath $ReleaseRoot --workpath (Join-Path $BuildRoot "setup") $SetupSpec
if ($LASTEXITCODE -ne 0) { throw "Tk installer build failed" }
$BuiltInstaller = Join-Path $ReleaseRoot "BetterCLX-Setup.exe"
if (Test-Path $BuiltInstaller) { Move-Item -Force $BuiltInstaller $Installer }

Write-Host "[4/4] Verifying release"
if (-not (Test-Path (Join-Path $AppDist "BetterCLX.exe"))) { throw "onedir executable missing" }
if (-not (Test-Path $Installer)) { throw "installer executable missing" }
Write-Host "Release root: $ReleaseRoot"
Write-Host "Tag: $Tag"
Write-Host "Onedir: $AppDist"
Write-Host "Installer: $Installer"

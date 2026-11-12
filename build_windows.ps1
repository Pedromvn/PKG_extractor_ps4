# SPDX-License-Identifier: GPL-2.0-or-later
param([string]$Python = "python", [switch]$SkipDependencies)
$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$BuildRoot = Join-Path $ProjectRoot "build-windows"
$VenvPython = Join-Path $BuildRoot "venv/Scripts/python.exe"

if ($env:OS -ne "Windows_NT") { throw "Build this executable on Windows x64." }
& $Python -m venv (Join-Path $BuildRoot "venv")
if ($LASTEXITCODE -ne 0) { throw "Failed to create the build environment." }
if (-not $SkipDependencies) {
    & $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements-build.txt")
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
}
# The worker needs real stdout/stderr for progress and errors. It is embedded
# inside the GUI and launched exclusively with CREATE_NO_WINDOW.
$WorkerOptions = @(
    "--noconfirm", "--clean", "--onedir", "--console",
    "--name", "PS4PkgExtractor-backend",
    "--hidden-import", "pkg_full", "--hidden-import", "pkg_crypto", "--hidden-import", "pkg_i18n",
    "--specpath", $BuildRoot,
    "--distpath", (Join-Path $BuildRoot "backend"),
    "--workpath", (Join-Path $BuildRoot "work-backend"),
    (Join-Path $ProjectRoot "pkgextract_backend.py")
)
& $VenvPython -m PyInstaller @WorkerOptions
if ($LASTEXITCODE -ne 0) { throw "Backend build failed." }
$WorkerDirectory = Join-Path $BuildRoot "backend/PS4PkgExtractor-backend"

# A Windows GUI-subsystem binary never creates a terminal on launch.
$Options = @(
    "--noconfirm", "--clean", "--onefile", "--windowed",
    "--add-data", "$WorkerDirectory;backend",
    "--name", "PS4PkgExtractor-windows-x64",
    "--hidden-import", "pkg_full", "--hidden-import", "pkg_crypto", "--hidden-import", "pkg_i18n",
    "--specpath", $BuildRoot,
    "--distpath", (Join-Path $BuildRoot "dist"),
    "--workpath", (Join-Path $BuildRoot "work")
)
foreach ($Asset in @("LICENSE", "NOTICE.md", "README.md", "README.pt-BR.md")) {
    $Options += @("--add-data", "$(Join-Path $ProjectRoot $Asset);.")
}
$Options += (Join-Path $ProjectRoot "pkgextract_gui.py")
& $VenvPython -m PyInstaller @Options
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
Write-Host "Executable: $(Join-Path $BuildRoot 'dist/PS4PkgExtractor-windows-x64.exe')"

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
# A console-subsystem executable retains working stdout/stderr for --backend.
# PyInstaller hides only a console owned by this app, keeping the GUI clean.
$Options = @(
    "--noconfirm", "--clean", "--onefile", "--console", "--hide-console", "hide-early",
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

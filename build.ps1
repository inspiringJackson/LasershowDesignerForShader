$ErrorActionPreference = "Stop"

$Version = "1.0.0"
$AppName = "LaserShowDesigner"
$BuildDir = "build"
$ReleaseDir = "release"

# 1. Run Unit Tests
Write-Host "Running Tests..." -ForegroundColor Cyan
pytest tests/ --junitxml=test_report.xml
if ($LASTEXITCODE -ne 0) {
    Write-Host "Tests failed!" -ForegroundColor Red
    exit 1
}

# 2. Run Static Code Analysis
Write-Host "Running Static Code Analysis (Bandit)..." -ForegroundColor Cyan
bandit -r src/ -ll -f json -o bandit_report.json
if ($LASTEXITCODE -ne 0) {
    Write-Host "Static analysis found high severity issues!" -ForegroundColor Red
    exit 1
}

# 3. Build Windows Executable
Write-Host "Building Windows Executable with PyInstaller..." -ForegroundColor Cyan
pyinstaller --noconfirm --onedir --windowed --icon "src/resources/logo.ico" --name $AppName --add-data "src/resources;resources" "src/main.py"

# Create release directory
if (!(Test-Path $ReleaseDir)) {
    New-Item -ItemType Directory -Path $ReleaseDir
}

# In a real environment, you would use InnoSetup Compiler (iscc) to build the .exe installer here:
# & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build_installer.iss
# Since ISCC might not be available, we will create a ZIP archive of the PyInstaller output as a fallback
$ZipName = "$ReleaseDir\$AppName-v$Version-windows-x64-standalone.zip"
if (Test-Path $ZipName) { Remove-Item $ZipName }
Compress-Archive -Path "dist\$AppName\*" -DestinationPath $ZipName
Write-Host "Created Standalone Zip: $ZipName" -ForegroundColor Green

# 4. Generate SHA256 Checksum
Write-Host "Generating SHA256 Checksums..." -ForegroundColor Cyan
$hash = Get-FileHash -Path $ZipName -Algorithm SHA256
$hash.Hash | Out-File "$ZipName.sha256"

# 5. Generate Release Notes
$ReleaseNotes = @"
# Laser Show Designer v$Version Release Notes

## 🚀 What's New
- Initial v1.0.0 Release of the Laser Show Designer software.
- Full support for real-time shader rendering.
- Complete timeline editing, keyframes, and automation tracking.
- Audio synchronization and custom UI components.

## 🛠️ System Requirements
- **Windows**: Windows 7 or later (x64)
- **macOS**: macOS 10.12 or later (Intel & Apple Silicon)

## 🔧 Known Issues
- macOS code signing and notarization require a valid Apple Developer ID.
- Windows EV Code Signing must be performed using the organization's physical USB token or HSM before public distribution.

## 📦 Downloads
- Windows Installer: `$AppName-v$Version-windows-x64.exe` (via Inno Setup)
- macOS Disk Image: `$AppName-v$Version-macos-universal.dmg` (Requires macOS build environment)
"@

$ReleaseNotes | Out-File "$ReleaseDir\ReleaseNotes-v$Version.md" -Encoding UTF8
Write-Host "Build complete! Artifacts are in the '$ReleaseDir' folder." -ForegroundColor Green

#!/bin/bash
set -e

VERSION="1.0.0"
APP_NAME="LaserShowDesigner"
RELEASE_DIR="release"

echo "=== Building $APP_NAME v$VERSION for macOS ==="

# 1. Run Tests & Static Analysis
echo "Running tests..."
pytest tests/ --junitxml=test_report.xml
echo "Running static analysis..."
bandit -r src/ -ll -f json -o bandit_report.json

# 2. Build with PyInstaller
echo "Building macOS application..."
pyinstaller --noconfirm --onedir --windowed --icon "src/resources/logo.png" --name "$APP_NAME" --add-data "src/resources:resources" "src/main.py"

# 3. Code Signing (Requires Apple Developer ID)
# Replace 'Developer ID Application: Your Name (Team ID)' with your actual certificate name
# codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name (Team ID)" "dist/$APP_NAME.app"

# 4. Create DMG
mkdir -p "$RELEASE_DIR"
DMG_NAME="$RELEASE_DIR/$APP_NAME-v$VERSION-macos-universal.dmg"
if [ -f "$DMG_NAME" ]; then
    rm "$DMG_NAME"
fi

# We use hdiutil or create-dmg tool to create the disk image
echo "Creating DMG package..."
# Option A: Simple hdiutil
hdiutil create -volname "$APP_NAME" -srcfolder "dist/$APP_NAME.app" -ov -format UDZO "$DMG_NAME"

# 5. Notarization (Requires Apple Developer Account)
# xcrun notarytool submit "$DMG_NAME" --keychain-profile "AC_PASSWORD" --wait

# 6. Generate Checksum
shasum -a 256 "$DMG_NAME" > "${DMG_NAME}.sha256"

echo "macOS Build Complete! Artifacts are in the $RELEASE_DIR directory."

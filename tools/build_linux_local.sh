#!/bin/bash
set -e

# Build CineBridge Pro Locally (Linux)
# This script mimics the GitHub Actions 'build-linux' job.

echo "🚀 Starting Local Linux Build..."

# 1. Check Dependencies
if ! command -v pyinstaller &> /dev/null; then
    echo "❌ PyInstaller not found! Please run: pip install pyinstaller"
    exit 1
fi

if ! command -v dpkg-deb &> /dev/null; then
    echo "❌ dpkg-deb not found! (Install 'dpkg-dev' or similar)"
    exit 1
fi

if ! command -v alien &> /dev/null; then
    echo "⚠️ 'alien' not found! RPM generation will be skipped."
    HAS_ALIEN=false
else
    HAS_ALIEN=true
fi

# 2. Clean previous builds
echo "🧹 Cleaning up..."
rm -rf dist build *.spec cinebridgepro_linux_amd64.deb cinebridgepro_linux_amd64.rpm

# 3. Create Icon
# Assumes assets/icon.png exists or is created from svg. 
# CI uses `convert`. We'll check if .png exists, if not try to convert.
if [ ! -f "assets/icon.png" ]; then
    if command -v convert &> /dev/null; then
        convert -background none -resize 512x512 assets/icon.svg assets/icon.png
        echo "✅ Icon converted."
    else
        echo "⚠️ 'convert' (ImageMagick) not found. Using default icon if available."
    fi
fi

# 4. Build with PyInstaller
echo "🔨 Building Binary with PyInstaller..."
# Note: We don't do the sed replacement for version here to avoid modifying source code locally.
# We just pass the current version string.
pyinstaller src/cinebridge.py --noconsole --onefile --name "cinebridgepro" --icon "assets/icon.png" --add-data "assets:assets"

# 5. Prepare Artifacts
echo "📦 Packaging..."
mkdir -p dist/deb/usr/local/bin
mkdir -p dist/deb/usr/share/applications
mkdir -p dist/deb/usr/share/icons/hicolor/512x512/apps
mkdir -p dist/deb/DEBIAN

cp dist/cinebridgepro dist/deb/usr/local/bin/
# Use a fallback if icon.png missing
if [ -f "assets/icon.png" ]; then
    cp assets/icon.png dist/deb/usr/share/icons/hicolor/512x512/apps/cinebridgepro.png
fi
chmod 755 dist/deb/usr/local/bin/cinebridgepro

# Prepare Portable Binary
cp dist/cinebridgepro dist/CineBridgePro_Linux_Portable
chmod +x dist/CineBridgePro_Linux_Portable

# Create Desktop Entry
cat <<EOF > dist/deb/usr/share/applications/cinebridgepro.desktop
[Desktop Entry]
Name=CineBridge Pro
Comment=DIT and Transcoding Suite
Exec=/usr/local/bin/cinebridgepro
Icon=cinebridgepro
Terminal=false
Type=Application
Categories=Video;AudioVideo;
EOF

# Create Control File
# Get version from version info or default
VERSION="4.16.7" 
cat <<EOF > dist/deb/DEBIAN/control
Package: cinebridgepro
Version: $VERSION
Section: video
Priority: optional
Architecture: amd64
Depends: ffmpeg, python3, libxcb-cursor0
Maintainer: Donovan Goodwin <ddg2goodwin@gmail.com>
Description: Open Source DIT & Post-Production Suite
 CineBridge Pro automates video ingest, proxy generation, and delivery.
EOF

# 6. Build DEB
echo "📦 Building DEB..."
dpkg-deb --build dist/deb cinebridgepro_linux_amd64.deb

# 7. Build RPM (if alien exists)
if [ "$HAS_ALIEN" = true ]; then
    echo "📦 Building RPM..."
    # alien requires root usually for ownership, but we can try with fakeroot if available or sudo
    if command -v fakeroot &> /dev/null; then
        fakeroot alien --to-rpm --scripts --keep-version cinebridgepro_linux_amd64.deb
    else
        echo "   (You might be asked for sudo password for 'alien')"
        sudo alien --to-rpm --scripts --keep-version cinebridgepro_linux_amd64.deb
    fi
    # Rename output
    mv cinebridgepro-*.rpm cinebridgepro_linux_amd64.rpm 2>/dev/null || true
fi

echo "✅ Build Complete!"
echo "📂 Artifacts:"
ls -lh cinebridgepro_linux_amd64.deb cinebridgepro_linux_amd64.rpm dist/CineBridgePro_Linux_Portable 2>/dev/null

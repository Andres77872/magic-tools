#!/usr/bin/env bash
# Build MyToolkit AppImage
set -e

APP=MyToolkit
VERSION=0.1.0
ARCH=x86_64
APPDIR="${APP}.AppDir"

# Clean previous builds
rm -rf "$APPDIR" "$APP-$VERSION-$ARCH.AppImage"

# Create AppDir structure
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copy application source
cp -r src "$APPDIR/usr/"

# Create launcher script inside AppDir
cat > "$APPDIR/usr/bin/${APP}" << 'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
python3 "$HERE/../src/main.py" "$@"
EOF
chmod +x "$APPDIR/usr/bin/${APP}"

# Desktop entry
cat > "$APPDIR/usr/share/applications/${APP}.desktop" << EOF
[Desktop Entry]
Type=Application
Name=${APP}
Exec=${APP}
Icon=${APP}
Categories=Utility;
EOF

# Icon (placeholder)
cp assets/${APP}.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/${APP}.png"

# Download linuxdeploy & plugin
wget -q "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-$ARCH.AppImage" -O linuxdeploy
chmod +x linuxdeploy
wget -q "https://github.com/linuxdeploy/linuxdeploy-plugin-python/releases/download/continuous/linuxdeploy-plugin-python-$ARCH.AppImage" -O linuxdeploy-plugin-python
chmod +x linuxdeploy-plugin-python

export VERSION="$VERSION"

# Build AppImage
./linuxdeploy --appdir "$APPDIR" --output appimage -i "$APPDIR/usr/share/icons/hicolor/256x256/apps/${APP}.png" -d "$APPDIR/usr/share/applications/${APP}.desktop" --plugin python

# Move resulting AppImage to root directory
mv *.AppImage "$APP-$VERSION-$ARCH.AppImage"

echo "\nCreated $APP-$VERSION-$ARCH.AppImage"

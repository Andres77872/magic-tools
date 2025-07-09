# MyToolkit

A minimal desktop utility packaged as an AppImage. Press your chosen shortcut key to launch it and access handy tools.

## Features (template)
* Opens quickly from a global shortcut.
* PyQt5 GUI (placeholder).
* Stand-alone AppImage – runs on most modern Linux distributions without installation.

## Building the AppImage

Requirements:
* bash
* wget
* python3 (>=3.8)
* The build script downloads `linuxdeploy` and `appimagetool` automatically.

```bash
./build-appimage.sh
```

The resulting file `MyToolkit-0.1.0-x86_64.AppImage` will appear in the project root.

## Running from source (for development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

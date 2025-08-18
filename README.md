# Magic Tools

AI-integrated desktop launcher with extensible tools and a modern PyQt5 UI.

## Features
- Global launcher with searchable tools grid
- AI chat with streaming responses and slash commands
- Configurable themes, hotkeys, and AI provider (OpenAI/local)
- Persisted settings and chat histories under XDG config

## Run from source

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

## Build AppImage (Linux)

Requirements:
- bash, wget, python3 (>=3.8)

```bash
cd appimage
./build-appimage.sh
```

The resulting file `MagicTools-0.1.0-x86_64.AppImage` will be placed in the project root.

#!/bin/bash
# Builds dist/DeckControl.app (portable: copy it anywhere; settings go in DeckControl-data next to it)
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -U pip setuptools wheel
pip install -q -r requirements.txt
pyinstaller --noconfirm --clean --windowed --name DeckControl \
  --osx-bundle-identifier com.deckcontrol.app \
  --add-data "deckcontrol/web:web" --add-data "deckcontrol/seed:seed" \
  --collect-submodules pynput --collect-submodules deckcontrol --hidden-import AppKit --hidden-import Quartz --hidden-import ApplicationServices \
  run.py
echo "Done: dist/DeckControl.app"

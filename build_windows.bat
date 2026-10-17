@echo off
python -m pip install -r requirements.txt || exit /b 1
python -m PyInstaller --noconfirm --clean --onefile --noconsole --name DeckControl ^
  --add-data "deckcontrol\web;web" --add-data "deckcontrol\seed;seed" ^
  --collect-submodules pynput --collect-submodules deckcontrol ^
  run.py || exit /b 1
echo.
echo Done: dist\DeckControl.exe  (portable - copy it anywhere; it creates DeckControl-data next to itself)

@echo off
rem Python 3.12: newer pre-release Pythons have no hidapi wheel and fail to compile it.
if not exist .venv312 py -3.12 -m venv .venv312 || goto :fail
.venv312\Scripts\python -m pip install -r requirements.txt || goto :fail
.venv312\Scripts\python -m PyInstaller --noconfirm --clean --onefile --noconsole --name DeckControl ^
  --add-data "deckcontrol\web;web" --add-data "deckcontrol\seed;seed" ^
  --collect-submodules pynput --collect-submodules deckcontrol ^
  run.py || goto :fail
echo.
echo Done: dist\DeckControl.exe  (portable - copy it anywhere; it creates DeckControl-data next to itself)
pause
exit /b 0
:fail
echo.
echo BUILD FAILED - see the error above.
pause
exit /b 1

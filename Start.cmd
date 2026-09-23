@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "soundset_app.py" %*
) else (
  python "soundset_app.py" %*
)
if errorlevel 1 (
  echo.
  echo See README.md for Python and dependency setup.
  pause
)

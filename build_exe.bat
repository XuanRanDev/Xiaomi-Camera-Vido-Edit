@echo off
setlocal

cd /d "%~dp0"

echo [1/3] Checking PyInstaller...
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo PyInstaller not found. Installing...
  python -m pip install pyinstaller
  if errorlevel 1 (
    echo Failed to install PyInstaller.
    exit /b 1
  )
)

echo [2/3] Cleaning old build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/3] Building EXE...
python -m PyInstaller ^
  --noconsole ^
  --onefile ^
  --name XiaomiCameraVideoEdit ^
  --add-data "config.json;." ^
  --add-data "icon.ico;." ^
  app\main.py

echo Done. Output: dist\XiaomiCameraVideoEdit.exe
endlocal

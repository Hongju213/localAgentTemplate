@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

title Local Agent Template - Build

echo.
echo ============================================================
echo   Local Agent Template - Windows Build
echo ============================================================
echo.

:: Step 1: Check Python
echo [1/5] Checking Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install Python 3.9+ and add to PATH.
    pause & exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do echo   Python %%i

:: Step 2: Virtual environment
echo.
echo [2/5] Setting up virtual environment...
if not exist "venv" python -m venv venv
call venv\Scripts\activate.bat
echo   venv activated

:: Step 3: Install dependencies
echo.
echo [3/5] Installing dependencies...
python -m pip install --upgrade pip --quiet
pip install -r ..\requirements.txt --quiet
pip install pyinstaller --quiet
echo   Dependencies installed

:: Step 4: Build EXE
echo.
echo [4/5] Building EXE with PyInstaller...

set ICON_OPT=
if exist "..\icon.ico" set ICON_OPT=--icon ..\icon.ico

pyinstaller --name LocalAgent ^
    --onefile ^
    --windowed ^
    %ICON_OPT% ^
    --add-data "..\config.py;." ^
    --add-data "..\models.py;." ^
    --add-data "..\worker.py;." ^
    --add-data "..\server.py;." ^
    --hidden-import fastapi ^
    --hidden-import uvicorn ^
    --hidden-import pydantic ^
    --hidden-import httpx ^
    --hidden-import pystray ^
    --collect-all fastapi ^
    --collect-all uvicorn ^
    ..\tray_app.py

if %errorlevel% neq 0 (
    echo ERROR: Build failed!
    pause & exit /b 1
)

:: Step 5: Verify
echo.
echo [5/5] Verifying...
if exist "dist\LocalAgent.exe" (
    echo.
    echo ============================================================
    echo   BUILD SUCCESS!
    echo   Output: dist\LocalAgent.exe
    echo ============================================================
) else (
    echo ERROR: Output not found
)

pause >nul

@echo off
cd /d "%~dp0"

echo Starting VideoLink-to-Text Server...
echo Please wait...

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment .venv not found!
    echo Please make sure .venv exists.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Process exited with error code: %errorlevel%
    pause
)

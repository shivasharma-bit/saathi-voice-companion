@echo off
REM Saathi — one-click start for Windows.
REM Double-click this file (or run it from PowerShell/cmd) any time you
REM want to run the server. It always does the right thing, in the right
REM folder, so you never have to remember the cd / activate / uvicorn
REM steps or hunt down a stuck Qdrant lock again.

REM Always operate from the folder this script itself lives in,
REM regardless of where you double-click it from.
cd /d "%~dp0"

echo === Saathi launcher ===
echo Working folder: %cd%

if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo ERROR: No .venv found here. Run this first, one time only:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo.
    echo No .env found — copying .env.example to .env now.
    copy .env.example .env >nul
    echo Edit .env to add your real RIME_API_KEY before your demo.
    echo.
)

call .venv\Scripts\activate.bat

REM Kill any leftover python process that might be holding the Qdrant
REM lock file from a server that wasn't stopped with Ctrl+C last time.
echo Clearing any stuck Qdrant lock from a previous run...
taskkill /F /IM python.exe >nul 2>&1
if exist "qdrant_data" (
    rmdir /s /q "qdrant_data" >nul 2>&1
)

echo.
echo Starting Saathi at http://localhost:8000
echo Press CTRL+C in this window to stop the server when you're done.
echo.

uvicorn backend.main:app

pause

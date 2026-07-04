@echo off
TITLE ClipForge AI Automated Launcher

echo ========================================================
echo       🚀 ClipForge AI — Automated Local Launcher       
echo ========================================================
echo.
echo ⚠️ PLEASE ENSURE PYTHON 3.11 OR HIGHER IS INSTALLED! 
echo If Python is not installed, the setup will fail.
echo.

cd /d "%~dp0"

echo [1/3] Checking backend environment...
cd backend

IF NOT EXIST ".venv\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment .venv ...
    python -m venv .venv
    IF ERRORLEVEL 1 (
        echo [ERROR] Failed to create virtual environment. Is Python installed and in PATH?
        pause
        exit /b 1
    )
)

echo [2/3] Installing/Updating dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel >nul
pip install -r requirements-core.txt

echo.
echo [3/3] Starting ClipForge AI...
echo --------------------------------------------------------
echo 🌐 Local Server:  http://127.0.0.1:8000
echo 📄 Dashboard:     Double-click 'dashboard.html' in the root folder, OR
echo 🔗 Direct link:   file:///%~dp0dashboard.html
echo --------------------------------------------------------
echo.
echo Keep this window open. Press Ctrl+C to stop the server.
echo.

:: Start FastAPI using Uvicorn
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

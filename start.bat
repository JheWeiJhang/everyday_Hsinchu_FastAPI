@echo off
cd /d "%~dp0"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3 from https://www.python.org
    pause
    exit /b 1
)

echo Checking dependencies...
python -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo Server starting at http://127.0.0.1:5000
echo Close the browser tab to stop the server automatically.
python main.py
echo.
echo Server stopped.
pause

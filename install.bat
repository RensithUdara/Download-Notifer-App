@echo off
echo Installing Download Notifier Dependencies...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH!
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

echo Python found. Installing required packages...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo Installation failed! Please check the error messages above.
    pause
    exit /b 1
)

echo.
echo Installation completed successfully!
echo You can now run the application with: python download_notifier.py
echo.
pause

@echo off
cd /d "%~dp0"
set OPTIONS_TRACKER_RELOAD=0
if not exist data mkdir data
set LOG_FILE=%~dp0data\startup.log
echo [%date% %time%] Starting Option Ledger from %CD% > "%LOG_FILE%"

where python >nul 2>nul
if %errorlevel%==0 (
  echo [%date% %time%] Using python from PATH >> "%LOG_FILE%"
  python start.py >> "%LOG_FILE%" 2>&1
  exit /b %errorlevel%
)

where py >nul 2>nul
if %errorlevel%==0 (
  echo [%date% %time%] Using py launcher >> "%LOG_FILE%"
  py -3 start.py >> "%LOG_FILE%" 2>&1
  exit /b %errorlevel%
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  echo [%date% %time%] Using Python312 from LOCALAPPDATA >> "%LOG_FILE%"
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" start.py >> "%LOG_FILE%" 2>&1
  exit /b %errorlevel%
)

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
  echo [%date% %time%] Using Python311 from LOCALAPPDATA >> "%LOG_FILE%"
  "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" start.py >> "%LOG_FILE%" 2>&1
  exit /b %errorlevel%
)

echo [%date% %time%] Python was not found. Install Python 3.10+ or add python.exe to PATH. >> "%LOG_FILE%"
exit /b 1

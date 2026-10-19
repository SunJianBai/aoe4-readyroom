@echo off
setlocal
cd /d "%~dp0"

set "APP_PYTHON=.venv\Scripts\python.exe"
if not exist "%APP_PYTHON%" (
    echo [AOE4ReadyRoom] Creating Python environment...
    where.exe python >nul 2>&1
    if not errorlevel 1 (
        python -m venv .venv
    ) else (
        where.exe py >nul 2>&1
        if errorlevel 1 goto :python_missing
        py -3 -m venv .venv
    )
    if errorlevel 1 goto :error
)

"%APP_PYTHON%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :error

rem Keep unrelated applications' Qt/ICU DLLs out of this process.
set "PATH=%~dp0.venv\Scripts;%SystemRoot%\System32;%SystemRoot%"
"%APP_PYTHON%" main.py
exit /b %errorlevel%

:python_missing
echo.
echo Python is required for start.bat. You can run dist\AOE4ReadyRoom.exe directly without Python.
pause
exit /b 1

:error
echo.
echo Start failed. Check the messages above.
pause
exit /b 1

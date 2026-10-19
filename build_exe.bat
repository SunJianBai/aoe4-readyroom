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

echo [AOE4ReadyRoom] Installing build dependencies...
"%APP_PYTHON%" -m pip install --disable-pip-version-check -r requirements.txt "pyinstaller>=6,<7"
if errorlevel 1 goto :error

echo [AOE4ReadyRoom] Building single-file Windows executable...
rem Isolate PATH so unrelated applications cannot leak incompatible Qt or ICU DLLs.
set "PATH=%~dp0.venv\Scripts;%SystemRoot%\System32;%SystemRoot%"
"%APP_PYTHON%" generate_icon.py
if errorlevel 1 goto :error
"%APP_PYTHON%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --specpath "build" ^
    --onefile ^
    --windowed ^
    --name AOE4ReadyRoom ^
    --icon "%~dp0assets\aoevillager.ico" ^
    --add-data "%~dp0assets\aoevillager.png;assets" ^
    --add-data "%~dp0assets\practice;assets\practice" ^
    --add-data "%~dp0assets\guides;assets\guides" ^
    --hidden-import pynput.keyboard._win32 ^
    --hidden-import pynput.mouse._win32 ^
    main.py
if errorlevel 1 goto :error

"%APP_PYTHON%" scripts\verify_bundle.py "%~dp0dist\AOE4ReadyRoom.exe"
if errorlevel 1 goto :error

echo.
echo Built: "%~dp0dist\AOE4ReadyRoom.exe"
pause
exit /b 0

:python_missing
echo.
echo Python is required only to build the EXE. You can run dist\AOE4ReadyRoom.exe directly without Python.
pause
exit /b 1

:error
echo.
echo Build failed. Check the messages above.
pause
exit /b 1

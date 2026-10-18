@echo off
setlocal
cd /d "%~dp0"

set "APP_PYTHON=.venv\Scripts\python.exe"
if not exist "%APP_PYTHON%" (
    echo [AOE4Toolbox] Creating Python environment...
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

echo [AOE4Toolbox] Installing build dependencies...
"%APP_PYTHON%" -m pip install --disable-pip-version-check -r requirements.txt "pyinstaller>=6,<7"
if errorlevel 1 goto :error

echo [AOE4Toolbox] Building single-file Windows executable...
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
    --name AOE4Toolbox ^
    --icon "assets\aoevillager.ico" ^
    --add-data "assets\aoevillager.png;assets" ^
    --add-data "web\hotkeys.html;web" ^
    --hidden-import pynput.keyboard._win32 ^
    --hidden-import pynput.mouse._win32 ^
    main.py
if errorlevel 1 goto :error

"%APP_PYTHON%" -c "from PyInstaller.archive.readers import CArchiveReader; import sys; names = CArchiveReader(sys.argv[1]).toc; bad = [name for name in names if name.lower().endswith('icuuc.dll')]; icon = any(name.replace('\\', '/').endswith('assets/aoevillager.png') for name in names); page = any(name.replace('\\', '/').endswith('web/hotkeys.html') for name in names); print('Unexpected bundled ICU DLL: ' + ', '.join(bad) if bad else 'Bundle DLL check passed'); print('Runtime icon asset bundled' if icon else 'Runtime icon asset missing'); print('Practice page bundled' if page else 'Practice page missing'); sys.exit(bool(bad) or not icon or not page)" "%~dp0dist\AOE4Toolbox.exe"
if errorlevel 1 goto :error

echo.
echo Built: "%~dp0dist\AOE4Toolbox.exe"
pause
exit /b 0

:python_missing
echo.
echo Python is required only to build the EXE. You can run dist\AOE4Toolbox.exe directly without Python.
pause
exit /b 1

:error
echo.
echo Build failed. Check the messages above.
pause
exit /b 1

@echo off
setlocal enabledelayedexpansion
title paparapa_tts - Setup
echo ============================================
echo   paparapa_tts Setup
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "REQS=%SCRIPT_DIR%requirements.txt"
set "ALL_GOOD=1"

:: -------------------------------------------
:: 1. Check Python
:: -------------------------------------------
echo [1/4] Checking Python...

set "PYTHON="
python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=python"
) else (
    py --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=py"
    )
)

if not defined PYTHON (
    echo   [FAIL] Python is not installed or not on PATH.
    echo   Please install Python 3.10+ from https://www.python.org/downloads/
    echo   Make sure to check "Add Python to PATH" during install.
    set "ALL_GOOD=0"
    goto :summary
)

for /f "tokens=2 delims= " %%v in ('!PYTHON! --version 2^>^&1') do set "PY_VER=%%v"
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)

if !PY_MAJOR! LSS 3 (
    echo   [FAIL] Python !PY_VER! found, but 3.10+ is required.
    set "ALL_GOOD=0"
    goto :summary
)
if !PY_MAJOR! EQU 3 if !PY_MINOR! LSS 10 (
    echo   [FAIL] Python !PY_VER! found, but 3.10+ is required.
    set "ALL_GOOD=0"
    goto :summary
)

echo   [OK] Python !PY_VER! (via !PYTHON!^)

:: -------------------------------------------
:: 2. Check / Install ffmpeg
:: -------------------------------------------
echo.
echo [2/4] Checking ffmpeg...

where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo   ffmpeg not found on PATH. Checking winget install...

    set "FFMPEG_FOUND=0"
    for /d %%p in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*") do (
        if exist "%%p" set "FFMPEG_FOUND=1"
    )

    if "!FFMPEG_FOUND!"=="0" (
        echo   ffmpeg is not installed. Installing via winget...
        echo.
        winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
        if errorlevel 1 (
            echo.
            echo   [FAIL] Could not install ffmpeg via winget.
            echo   Please install ffmpeg manually: https://ffmpeg.org/download.html
            echo   and make sure ffmpeg.exe is on your PATH.
            set "ALL_GOOD=0"
            goto :summary
        )
        echo.
        echo   [OK] ffmpeg installed via winget.
    ) else (
        echo   [OK] ffmpeg found in winget packages (not on PATH, script will find it automatically^).
    )
) else (
    for /f "tokens=3 delims= " %%v in ('ffmpeg -version 2^>^&1 ^| findstr /B "ffmpeg version"') do set "FF_VER=%%v"
    echo   [OK] ffmpeg !FF_VER!
)

:: ffprobe ships with ffmpeg - if ffmpeg was found above, ffprobe is there too

:: -------------------------------------------
:: 3. Create venv if needed
:: -------------------------------------------
echo.
echo [3/4] Checking virtual environment...

if exist "%VENV_DIR%\Scripts\python.exe" (
    echo   [OK] venv exists at .venv\
) else (
    echo   Creating virtual environment...
    !PYTHON! -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo   [FAIL] Could not create virtual environment.
        set "ALL_GOOD=0"
        goto :summary
    )
    echo   [OK] venv created at .venv\
)

:: -------------------------------------------
:: 4. Install Python dependencies
:: -------------------------------------------
echo.
echo [4/4] Checking Python dependencies...

set "NEED_INSTALL=0"
for /f "usebackq tokens=1" %%r in ("%REQS%") do (
    "%VENV_DIR%\Scripts\pip.exe" show %%r >nul 2>&1
    if errorlevel 1 set "NEED_INSTALL=1"
)

if "!NEED_INSTALL!"=="1" (
    echo   Installing dependencies...
    "%VENV_DIR%\Scripts\pip.exe" install -r "%REQS%" --quiet
    if errorlevel 1 (
        echo   [FAIL] Could not install Python dependencies.
        set "ALL_GOOD=0"
        goto :summary
    )
    echo   [OK] Dependencies installed.
) else (
    echo   [OK] All dependencies already installed.
)

:: -------------------------------------------
:: Summary
:: -------------------------------------------
:summary
echo.
echo ============================================
if "!ALL_GOOD!"=="1" (
    echo   Setup complete. You are ready to go.
    echo.
    echo   Usage:
    echo     .venv\Scripts\python.exe paparapa_tts.py "video.mkv"
    echo.
    echo   Options:
    echo     -v David        Use a specific TTS voice
    echo     -r 200          Speech rate in WPM (default: 175^)
    echo     -o output.mkv   Custom output filename
    echo     --list-voices   Show available TTS voices
) else (
    echo   Setup incomplete. Please fix the issues above and run again.
)
echo ============================================
echo.
pause

@echo off
setlocal

cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] uv was not found in PATH.
    echo Install uv or add it to PATH, then run this file again.
    pause
    exit /b 1
)

rem better_clx.main handles process-level UAC elevation before creating the GUI.
uv run clx
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Better CLX exited with code %EXIT_CODE%.
    pause
)

endlocal & exit /b %EXIT_CODE%

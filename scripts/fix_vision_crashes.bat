@echo off
REM Fix for Vision Model Crashes
REM Solutions for "model runner has unexpectedly stopped" errors

REM Change to script directory
cd /d "%~dp0"

REM Set UTF-8 encoding for emoji support
chcp 65001 >nul 2>&1

echo ================================================
echo VISION MODEL CRASH FIX
echo ================================================
echo.
echo The vision model (llava:7b) is crashing due to
echo resource limitations. Here are your options:
echo.
echo [1] Restart Ollama (clears stuck state)
echo [2] Disable vision processing (skip AI image analysis)
echo [3] Use CPU-only mode (slower but stable)
echo [4] Check Ollama logs
echo [5] Exit
echo.
set /p CHOICE=Enter choice (1-5):

if "%CHOICE%"=="1" goto RESTART
if "%CHOICE%"=="2" goto DISABLE
if "%CHOICE%"=="3" goto CPU_ONLY
if "%CHOICE%"=="4" goto LOGS
if "%CHOICE%"=="5" goto END

:RESTART
echo.
echo [1/2] Stopping Ollama...
taskkill /F /IM ollama.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2/2] Starting Ollama...
start "" "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
timeout /t 3 /nobreak >nul

echo.
echo Done! Ollama restarted.
echo Try running the pipeline again.
goto END

:DISABLE
echo.
echo Disabling vision processing in .env...
powershell -Command "(Get-Content .env) -replace 'DISABLE_VISION_PROCESSING=false', 'DISABLE_VISION_PROCESSING=true' | Set-Content .env"
echo.
echo Done! Vision processing disabled.
echo.
echo The pipeline will:
echo   - Still extract images from PDFs
echo   - Skip AI analysis of images
echo   - Use much less VRAM
echo   - Run faster
echo.
echo To re-enable later, change DISABLE_VISION_PROCESSING=false in .env
goto END

:CPU_ONLY
echo.
echo Setting Ollama to CPU-only mode...
echo.
echo Add this environment variable:
echo   OLLAMA_NUM_GPU=0
echo.
echo Then restart Ollama:
echo   1. Stop: taskkill /F /IM ollama.exe
echo   2. Set: set OLLAMA_NUM_GPU=0
echo   3. Start: ollama serve
echo.
echo This will be slower but won't use GPU at all.
goto END

:LOGS
echo.
echo Checking Ollama logs...
echo.
echo Logs are typically in:
echo   %LOCALAPPDATA%\Ollama\logs\
echo.
if exist "%LOCALAPPDATA%\Ollama\logs\" (
    dir /b /o-d "%LOCALAPPDATA%\Ollama\logs\"
    echo.
    echo View the latest log file for details.
) else (
    echo Log directory not found.
)
goto END

:END
echo.
echo ================================================
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PARAMS=%*"
if "%PARAMS%"=="" set "PARAMS=play"

REM 1. Tenta ambiente virtual .venv local
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe app.py %PARAMS%
    exit /b %ERRORLEVEL%
)

REM 2. Tenta uv
where uv >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    uv run python app.py %PARAMS%
    exit /b %ERRORLEVEL%
)

REM 3. Tenta py launcher
py -3 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 app.py %PARAMS%
    exit /b %ERRORLEVEL%
)

REM 4. Tenta python
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python app.py %PARAMS%
    exit /b %ERRORLEVEL%
)

echo Python não encontrado. Instale o Python 3.10+ para jogar.
pause
exit /b 1

@echo off
setlocal
rem Work in this script's folder, the project, also when it is started elsewhere: Run as administrator starts batch files in C:\Windows\System32.
cd /d "%~dp0"
set "CURRENT_DIR=%CD%"
echo ***** Current directory: "%CURRENT_DIR%" *****
set "PYTHONPATH=%CURRENT_DIR%"

rem set HF_ENDPOINT=https://hf-mirror.com

rem Drop stray spaces from the host, such as the one a cmd one-liner keeps before its second command.
if defined MPT_WEBUI_HOST set "MPT_WEBUI_HOST=%MPT_WEBUI_HOST: =%"
if not defined MPT_WEBUI_HOST set "MPT_WEBUI_HOST=127.0.0.1"
if not defined MPT_WEBUI_PORT set "MPT_WEBUI_PORT=8501"

set "STREAMLIT_CMD="
rem Quote only the python.exe path: quoting the whole assignment leaves the path itself unquoted, and a ")" or "&" in it breaks this block.
if exist "%CURRENT_DIR%\.venv\Scripts\python.exe" (
    set STREAMLIT_CMD="%CURRENT_DIR%\.venv\Scripts\python.exe" -m streamlit
) else if exist "%CURRENT_DIR%\lib\python\python.exe" (
    set STREAMLIT_CMD="%CURRENT_DIR%\lib\python\python.exe" -m streamlit
) else (
    where uv >nul 2>nul
    if not errorlevel 1 set "STREAMLIT_CMD=uv run streamlit"
)

if not defined STREAMLIT_CMD (
    where streamlit >nul 2>nul
    if not errorlevel 1 (
        echo ***** Warning: using streamlit from PATH. If dependencies fail, run 'uv sync --frozen' first. *****
        set "STREAMLIT_CMD=streamlit"
    )
)

if not defined STREAMLIT_CMD (
    echo ***** Neither project Python, uv, nor streamlit was found. Please install dependencies first. *****
    pause
    exit /b 1
)

set "SELECTED_WEBUI_PORT="
rem webui_port.ps1 resolves the host address, frees the preferred port when the
rem occupier is a previous instance of this WebUI (matched by its command line),
rem never stops foreign applications, and otherwise falls back to 8502-8599.
rem ExclusiveAddressUse in the probe: without it, a 0.0.0.0 bind succeeds even
rem when a program listens on the same port at 127.0.0.1, and the browser would
rem open that program.
for /f %%P in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%CURRENT_DIR%\webui_port.ps1"') do set "SELECTED_WEBUI_PORT=%%P"

if not defined SELECTED_WEBUI_PORT (
    echo ***** No available WebUI port found in 8501-8599 for %MPT_WEBUI_HOST%. *****
    echo ***** If Windows reports WinError 10013, check reserved ports: netsh interface ipv4 show excludedportrange protocol=tcp *****
    pause
    exit /b 1
)

if not "%SELECTED_WEBUI_PORT%"=="%MPT_WEBUI_PORT%" (
    echo ***** Port %MPT_WEBUI_PORT% is unavailable, using %SELECTED_WEBUI_PORT% instead. *****
)
set "MPT_WEBUI_PORT=%SELECTED_WEBUI_PORT%"

rem 0.0.0.0 makes the WebUI listen on every network interface, but Windows does not connect to 0.0.0.0, so the browser opens 127.0.0.1.
set "BROWSER_WEBUI_HOST=%MPT_WEBUI_HOST%"
if "%MPT_WEBUI_HOST%"=="0.0.0.0" set "BROWSER_WEBUI_HOST=127.0.0.1"

echo ***** WebUI address: http://%BROWSER_WEBUI_HOST%:%MPT_WEBUI_PORT% *****
%STREAMLIT_CMD% run .\webui\Main.py --server.address=%MPT_WEBUI_HOST% --server.port=%MPT_WEBUI_PORT% --browser.serverAddress=%BROWSER_WEBUI_HOST% --browser.gatherUsageStats=False --client.toolbarMode=minimal --logger.hideWelcomeMessage=True --server.showEmailPrompt=False --server.enableCORS=True

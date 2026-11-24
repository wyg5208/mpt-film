@echo off
setlocal
rem ============================================================
rem  ChangoFilm one-click RESTART launcher for the NEW web UI
rem  (FastAPI backend + embedded React app, single origin).
rem
rem  Usage:
rem    start-web.bat       Restart backend on 8080 and open the
rem                        embedded new UI (http://127.0.0.1:8080).
rem    start-web.bat dev   Also restart the Vite dev server (5173)
rem                        with hot reload, then open localhost:5173.
rem
rem  Restart semantics: a listener on the target port is stopped
rem  ONLY when its command line matches this project (main.py web
rem  or vite). Foreign applications are NEVER killed; the launcher
rem  aborts with a clear message instead of fighting for the port.
rem
rem  ASCII-only on purpose: Windows console codepages garble CJK.
rem  Uses ping for delays: timeout /t hangs when stdin is redirected.
rem ============================================================
cd /d "%~dp0"
set "ROOT=%CD%"
set "BACKEND_PORT=8080"
set "FRONTEND_PORT=5173"
set "MODE=%~1"
set "MODE_DESC=embedded UI (backend serves the built React app)"
if /I "%MODE%"=="dev" set "MODE_DESC=dev (Vite hot reload + backend)"

echo ============================================================
echo  ChangoFilm restart launcher  -  mode: %MODE_DESC%
echo ============================================================
echo  backend port: %BACKEND_PORT%   frontend dev port: %FRONTEND_PORT%
echo.

rem ---- 1. stop a previous backend of THIS project on the port ----
call :kill_port %BACKEND_PORT% "main\.py web" backend
if %KP_FOREIGN% EQU 1 goto fail_foreign_backend
if %KP_KILLED% GTR 0 call :wait_free %BACKEND_PORT%

rem ---- 2. project interpreter (never a machine-global python) ----
set "PYTHON="
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not defined PYTHON if exist "%ROOT%\lib\python\python.exe" set "PYTHON=%ROOT%\lib\python\python.exe"
if not defined PYTHON goto fail_no_python
echo [INFO] python: %PYTHON%

rem ---- 3. start the backend window -------------------------------
start "ChangoFilm Web %BACKEND_PORT%" /D "%ROOT%" cmd /k ""%PYTHON%" -X utf8 main.py web"

rem ---- 4. dev mode: restart the Vite dev server as well ----------
if /I not "%MODE%"=="dev" goto wait_backend
call :kill_port %FRONTEND_PORT% "vite" vite-dev
if %KP_FOREIGN% EQU 1 goto skip_vite_foreign
if %KP_KILLED% GTR 0 call :wait_free %FRONTEND_PORT%
start "ChangoFilm Vite Dev %FRONTEND_PORT%" /D "%ROOT%frontend" cmd /k "npm run dev"
goto wait_backend

:skip_vite_foreign
echo [WARN] frontend dev server NOT started: port %FRONTEND_PORT% is foreign-owned.
echo [INFO] continuing with the backend only; the embedded UI will open.

:wait_backend
echo.
echo [WAIT] polling backend http://127.0.0.1:%BACKEND_PORT% ...
set /a TRIES=0
:poll_backend
ping -n 2 127.0.0.1 >nul
set /a TRIES+=1
set "CODE="
for /f %%i in ('curl -s -m 2 -o NUL -w "%%{http_code}" http://127.0.0.1:%BACKEND_PORT%/') do set "CODE=%%i"
if "%CODE%"=="200" goto backend_ready
if %TRIES% GEQ 60 goto backend_timeout
goto poll_backend

:backend_ready
echo [ OK ] backend is up after %TRIES% poll(s).
goto open_browser

:backend_timeout
echo [WARN] backend not ready after %TRIES% polls - check its window for errors.

:open_browser
if /I not "%MODE%"=="dev" goto open_embedded
echo.
echo [WAIT] polling Vite dev http://localhost:%FRONTEND_PORT% ...
set /a TRIES=0
:poll_frontend
ping -n 2 127.0.0.1 >nul
set /a TRIES+=1
set "CODE="
for /f %%i in ('curl -s -m 2 -o NUL -w "%%{http_code}" http://localhost:%FRONTEND_PORT%/') do set "CODE=%%i"
if "%CODE%"=="200" goto frontend_ready
if %TRIES% GEQ 45 goto frontend_timeout
goto poll_frontend

:frontend_ready
start "" http://localhost:%FRONTEND_PORT%
echo [ OK ] opened http://localhost:%FRONTEND_PORT%  (dev UI, hot reload)
goto done

:frontend_timeout
echo [WARN] Vite dev not ready after %TRIES% polls - opening the embedded UI instead.
start "" http://127.0.0.1:%BACKEND_PORT%
echo [ OK ] opened http://127.0.0.1:%BACKEND_PORT%
goto done

:open_embedded
start "" http://127.0.0.1:%BACKEND_PORT%
echo [ OK ] opened http://127.0.0.1:%BACKEND_PORT%  (embedded new UI)
goto done

:done
echo.
echo Close the spawned windows or press Ctrl+C inside them to stop.
echo Re-run this script anytime to restart.
echo.
pause
exit /b 0

:fail_foreign_backend
echo.
echo [FAIL] port %BACKEND_PORT% is held by another application (not main.py web).
echo        It was NOT killed. Free the port or edit BACKEND_PORT in this script.
echo.
pause
exit /b 1

:fail_no_python
echo.
echo [FAIL] no project interpreter found (.venv or lib\python).
echo        Create it first with: uv sync --frozen
echo.
pause
exit /b 1

rem ---------------------------------------------------------------
rem :kill_port PORT "identity-regex" label
rem Stops LISTENING pids on PORT whose command line matches the
rem identity regex. Foreign owners set KP_FOREIGN and survive.
rem ---------------------------------------------------------------
:kill_port
set "KP_PORT=%~1"
set "KP_REGEX=%~2"
set "KP_LABEL=%~3"
set "KP_KILLED=0"
set "KP_FOREIGN=0"
set "KP_SEEN= "
for /f "tokens=5" %%p in ('netstat -ano -p tcp ^| findstr /R /C:":%KP_PORT% .*LISTENING"') do call :kill_one %%p
if %KP_KILLED% EQU 0 if %KP_FOREIGN% EQU 0 echo [INFO] port %KP_PORT% free - nothing to restart
goto :eof

:kill_one
echo %KP_SEEN%| findstr /C:" %~1 " >nul
if errorlevel 1 set "KP_SEEN=%KP_SEEN%%~1 "
if errorlevel 1 goto kill_one_checked
goto :eof

:kill_one_checked
set "CPID=%~1"
powershell -NoProfile -Command "$p=Get-CimInstance Win32_Process -Filter ('ProcessId=%CPID%'); if(-not $p){exit 0}; if($p.CommandLine -match '%KP_REGEX%'){exit 1}; exit 2"
set "KP_RC=%ERRORLEVEL%"
if "%KP_RC%"=="1" goto kp_kill
if "%KP_RC%"=="2" goto kp_foreign
rem rc 0 (process already gone) and 9009 (powershell missing) land here: safe skip
goto kp_skip

:kp_kill
taskkill /F /PID %CPID% >nul 2>&1
echo [ OK ] stopped previous %KP_LABEL% (pid %CPID%) on port %KP_PORT%
set /a KP_KILLED+=1
goto :eof

:kp_foreign
echo [WARN] port %KP_PORT% is held by a foreign application (pid %CPID%) - NOT stopped
set KP_FOREIGN=1
goto :eof

:kp_skip
echo [SKIP] pid %CPID% on port %KP_PORT% no longer exists - ignored
goto :eof

rem ---------------------------------------------------------------
rem :wait_free PORT - block briefly until PORT leaves LISTENING
rem ---------------------------------------------------------------
:wait_free
set "WF_PORT=%~1"
set /a WF_TRIES=0
:wf_loop
netstat -ano -p tcp | findstr /R /C:":%WF_PORT% .*LISTENING" >nul
if errorlevel 1 goto wf_done
set /a WF_TRIES+=1
if %WF_TRIES% GEQ 10 goto wf_timeout
ping -n 2 127.0.0.1 >nul
goto wf_loop
:wf_timeout
echo [WARN] port %WF_PORT% still shows LISTENING - the start below may hit a bind error
:wf_done
goto :eof

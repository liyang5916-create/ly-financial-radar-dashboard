@echo off
setlocal EnableExtensions

chcp 65001 >nul
cd /d "%~dp0" || (
    echo Failed to enter project directory: %~dp0
    pause
    exit /b 1
)

echo ============================================================
echo Finance Radar Web Service
echo ============================================================

set "PYTHON_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE="
)

if not defined PYTHON_EXE (
    where python.exe >nul 2>nul
    if not errorlevel 1 set "PYTHON_EXE=python.exe"
)

if not defined PYTHON_EXE (
    where py.exe >nul 2>nul
    if not errorlevel 1 set "PYTHON_EXE=py.exe -3"
)

if not defined PYTHON_EXE (
    echo Python was not found.
    echo Install Python 3.10 or later, or run this from the Codex bundled runtime.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

%PYTHON_EXE% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
    echo Python 3.10 or later is required.
    pause
    exit /b 1
)

for %%P in (7890 7897 10809 10808 20171 8888 8080) do (
    powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient; try {$a=$c.BeginConnect('127.0.0.1',%%P,$null,$null); if($a.AsyncWaitHandle.WaitOne(250,$false) -and $c.Connected){exit 0}else{exit 1}} finally {$c.Close()}" >nul 2>nul
    if not errorlevel 1 (
        set "HTTP_PROXY=http://127.0.0.1:%%P"
        set "HTTPS_PROXY=http://127.0.0.1:%%P"
        set "http_proxy=http://127.0.0.1:%%P"
        set "https_proxy=http://127.0.0.1:%%P"
        echo Proxy: http://127.0.0.1:%%P
        goto proxy_done
    )
)
:proxy_done

echo URL: http://127.0.0.1:5000
echo Press Ctrl+C to stop the service.
echo ============================================================

%PYTHON_EXE% main.py
pause

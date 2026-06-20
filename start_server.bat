@echo off
chcp 65001 >nul
echo ========================================
echo   财经日报雷达 - Web 服务器启动
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 设置环境变量...
set PYTHONPATH=%cd%

echo [2/3] 启动 Flask 服务器...
echo.
echo 服务已启动！可通过以下方式访问：
echo.
echo   本地访问：
echo   - http://127.0.0.1:5000/tabs  (新看板)
echo   - http://127.0.0.1:5000/      (原看板)
echo.
echo   局域网访问（同一 WiFi）：
echo   - http://[你的电脑IP]:5000/tabs
echo.
echo   跨网络访问（需要 cpolar）：
echo   - 请先运行 start_cpolar.bat
echo.
echo ========================================
echo 按 Ctrl+C 停止服务器
echo ========================================
echo.

python -m web.app

pause

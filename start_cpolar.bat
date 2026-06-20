@echo off
chcp 65001 >nul
echo ========================================
echo   cpolar 内网穿透 - 启动脚本
echo ========================================
echo.

REM 检查 cpolar 是否已安装
where cpolar >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [错误] cpolar 未安装
    echo.
    echo 请先完成以下步骤：
    echo 1. 访问 https://www.cpolar.com/ 注册账号
    echo 2. 下载并安装 cpolar
    echo 3. 运行 cpolar authtoken [你的token]
    echo.
    echo 详细说明请查看 CPOLAR使用说明.md
    pause
    exit /b 1
)

echo [1/2] 检测 Flask 服务器状态...
powershell -Command "$test = Test-NetConnection -ComputerName 127.0.0.1 -Port 5000 -InformationLevel Quiet -WarningAction SilentlyContinue; if (-not $test) { Write-Host '[警告] Flask 服务器未启动，请先运行 start_server.bat'; exit 1 }"

if %ERRORLEVEL% NEQ 0 (
    pause
    exit /b 1
)

echo [2/2] 启动 cpolar 隧道（映射端口 5000）...
echo.
echo ========================================
echo cpolar 隧道已建立！
echo 复制下方的公网地址，即可在任何设备访问
echo ========================================
echo.

cpolar http 5000

pause

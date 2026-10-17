@echo off
chcp 65001 >nul
title 书桥 BOOKBRIDGE + AI Agent 启动器

echo ============================================================
echo   书桥 BOOKBRIDGE + AI Agent 一键启动
echo ============================================================
echo.

REM 优先使用 Anaconda Python（已装好依赖）
set PYTHON=D:\anaconda\python.exe
if not exist "%PYTHON%" (
    set PYTHON=C:\Users\20752\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
)
if not exist "%PYTHON%" (
    echo [错误] 找不到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

echo 使用 Python: %PYTHON%
echo.

REM 检查依赖
cd /d "%~dp0backend"
"%PYTHON%" -c "import fastapi, uvicorn, sqlalchemy" 2>nul
if errorlevel 1 (
    echo [安装依赖中...]
    "%PYTHON%" -m pip install fastapi==0.115.0 "uvicorn[standard]==0.30.6" sqlalchemy==2.0.35 pydantic==2.9.2 python-dateutil==2.9.0 -i https://mirrors.huaweicloud.com/repository/pypi/simple --quiet
    echo 依赖安装完成。
    echo.
)

echo ============================================================
echo   服务启动中...
echo.
echo   访问地址: http://localhost:8000/
echo   接口文档: http://localhost:8000/docs
echo   AI Agent: 点击页面右下角 🤖 按钮
echo.
echo   按 Ctrl+C 停止服务
echo ============================================================
echo.

"%PYTHON%" run_server.py
pause
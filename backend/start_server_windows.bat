@echo off
REM BugSeek 后端启动脚本（Windows 单进程模式）

echo ========================================
echo 启动 BugSeek 后端服务
echo ========================================
echo.

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python 环境
    pause
    exit /b 1
)

REM 启动服务（单进程模式，避免 Windows multiprocessing 问题）
echo [信息] 启动后端服务...
echo [信息] 地址: http://127.0.0.1:8000
echo [信息] API 文档: http://127.0.0.1:8000/docs
echo.

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

pause
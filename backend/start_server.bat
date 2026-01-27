@echo off
REM BugSeek 后端启动脚本（Windows）

echo ========================================
echo 启动 BugSeek 后端服务
echo ========================================
echo.

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python 环境
    pause
    exit /b 1
)

REM 检查虚拟环境
if not exist "venv" (
    echo [信息] 创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖
echo [信息] 安装依赖...
pip install -r requirements.txt

REM 启动服务（监听 0.0.0.0 以支持 WSL 跨网络访问）
echo [信息] 启动后端服务...
echo [信息] 地址: http://0.0.0.0:8000
echo [信息] Windows 访问: http://127.0.0.1:8000
echo [信息] API 文档: http://127.0.0.1:8000/docs
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
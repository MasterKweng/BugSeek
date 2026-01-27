#!/bin/bash
# BugSeek 后端启动脚本（Linux/WSL）

echo "========================================"
echo "启动 BugSeek 后端服务"
echo "========================================"
echo ""

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 Python 环境"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "[信息] 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "[信息] 安装依赖..."
pip install -r requirements.txt

# 启动服务（监听 0.0.0.0 以支持跨网络访问）
echo "[信息] 启动后端服务..."
echo "[信息] 地址: http://0.0.0.0:8000"
echo "[信息] WSL 访问: http://localhost:8000"
echo "[信息] Windows 访问: http://127.0.0.1:8000"
echo "[信息] API 文档: http://127.0.0.1:8000/docs"
echo ""

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
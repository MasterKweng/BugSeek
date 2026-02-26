@echo off
chcp 65001 >nul
echo ========================================
echo 启动 Celery Worker (Windows)
echo ========================================
echo.

REM 加载 .env 文件
echo 加载环境变量配置...
for /f "tokens=*" %%a in (%~dp0.env) do set %%a
echo 环境变量加载完成
echo.

REM 设置 Hugging Face 镜像源（加速国内下载）
set HF_ENDPOINT=https://hf-mirror.com
echo Hugging Face 镜像: %HF_ENDPOINT%
echo.

celery -A app.celery_config worker --loglevel=INFO --logfile=%cd%\logs\celery_worker.log --pool=threads --without-mingle --without-gossip

pause
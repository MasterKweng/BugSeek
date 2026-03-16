@echo off
chcp 65001 >nul
echo ========================================
echo 启动 Celery Worker (Windows)
echo ========================================
echo.

REM 设置环境变量（默认为 dev）
if "%APP_ENV%"=="" (
    set APP_ENV=dev
)
echo 当前环境: %APP_ENV%
echo.

REM 加载对应的 .env 文件
echo 加载环境变量配置: .env.%APP_ENV%
for /f "tokens=*" %%a in (%~dp0.env.%APP_ENV%) do set %%a
echo 环境变量加载完成
echo.

REM 设置 Hugging Face 镜像源（加速国内下载）
set HF_ENDPOINT=https://hf-mirror.com
echo Hugging Face 镜像: %HF_ENDPOINT%
echo.

celery -A app.celery_config worker --loglevel=INFO --logfile=%cd%\logs\celery_worker.log --pool=threads --without-mingle --without-gossip

pause
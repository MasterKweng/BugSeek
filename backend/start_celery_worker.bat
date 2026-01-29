@echo off
chcp 65001 >nul
echo ========================================
echo 启动 Celery Worker
echo ========================================
echo.

celery -A app.celery_config worker --loglevel=info --pool=solo

pause
#!/bin/bash
echo "========================================"
echo "启动 Celery Worker"
echo "========================================"
echo ""

# 设置 Hugging Face 镜像源（加速国内下载）
export HF_ENDPOINT=https://hf-mirror.com
echo "Hugging Face 镜像: $HF_ENDPOINT"
echo ""

celery -A app.celery_config worker --loglevel=info --pool=solo
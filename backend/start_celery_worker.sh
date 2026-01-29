#!/bin/bash
echo "========================================"
echo "启动 Celery Worker"
echo "========================================"
echo ""

celery -A app.celery_config worker --loglevel=info --pool=solo
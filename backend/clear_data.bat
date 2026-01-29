@echo off
chcp 65001 >nul
REM 清除文档、接口、脚本数据工具
REM 使用方法: clear_data.bat [选项]

echo ========================================
echo   清除文档、接口、脚本数据工具
echo ========================================
echo.

if "%1"=="" goto usage

python clear_documents_endpoints_scripts.py %*
goto end

:usage
echo 使用方法：
echo.
echo 1. 列出所有项目：
echo    clear_data.bat --list
echo.
echo 2. 查看项目统计：
echo    clear_data.bat --project-id 1 --stats
echo.
echo 3. 清除项目数据（需要确认）：
echo    clear_data.bat --project-id 1
echo.
echo 4. 强制清除项目数据（跳过确认）：
echo    clear_data.bat --project-id 1 --force
echo.

:end
pause
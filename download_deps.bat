@echo off
title 下载 LAN Doc Hub 依赖包

echo.
echo ========================================
echo   LAN Doc Hub - 离线依赖下载工具
echo ========================================
echo.
echo 此脚本会将所有 Python 依赖包下载到 vendor/ 目录。
echo 复制整个项目到局域网机器后，run.bat 将从本地安装，无需联网。
echo.
echo 注意：下载的包针对当前 Python 版本（与开发机一致）。
echo 目标机器应安装相同 Python 版本，否则需重新运行本脚本。
echo ========================================
echo.

python --version
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

echo.
echo 正在创建 vendor 目录...
if not exist vendor mkdir vendor

echo 正在下载依赖包...
python -m pip download -r requirements.txt -d vendor/

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   下载完成！依赖包已保存到 vendor/ 目录
    echo ========================================
) else (
    echo.
    echo [错误] 下载失败，请检查网络连接后重试
)

echo.
pause

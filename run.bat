@echo off
title LAN Doc Hub

echo.
echo ========================================
echo   LAN Doc Hub 正在启动...
echo ========================================
echo.
echo 服务启动后，请在浏览器中访问：
echo.
echo   本机访问: http://127.0.0.1:5000
echo   局域网内: http://你的IP地址:5000
echo.
echo 按 Ctrl+C 或关闭此窗口即可停止服务
echo ========================================
echo.

echo 正在检查依赖...
if exist vendor\*.whl (
    echo   [离线模式] 从 vendor/ 本地安装...
    pip install -r requirements.txt --no-index --find-links=vendor/ -q
) else (
    echo   [在线模式] vendor/ 为空，从网络安装...
    pip install -r requirements.txt -q
)
echo.
echo 正在启动 LAN Doc Hub...
python app.py

pause

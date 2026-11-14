@echo off
chcp 65001 > nul
echo =================================================================
echo   KHỞI ĐỘNG RPLIDAR C1M1 WEB BRIDGE SERVER (WINDOWS / MOCK)
echo =================================================================
python "%~dp0..\bridge\lidar_bridge_server.py" --mock --port 8080 %*
pause

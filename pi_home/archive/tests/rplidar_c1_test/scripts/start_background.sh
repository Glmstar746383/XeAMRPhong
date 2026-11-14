#!/usr/bin/env bash
# ==============================================================================
# start_background.sh - Chạy ngầm LiDAR C1 và Web Bridge trong session tmux
# ==============================================================================

tmux kill-session -t agv_lidar 2>/dev/null || true
pkill -f sllidar_node 2>/dev/null || true
pkill -f lidar_bridge_server.py 2>/dev/null || true
sleep 1

# Cửa sổ 1: Driver LiDAR quét laser thật
tmux new-session -d -s agv_lidar -n lidar \
  "bash -c 'source /opt/ros/jazzy/setup.bash && source /home/khangho/rplidar_c1_ws/install/setup.bash && ros2 launch sllidar_ros2 sllidar_c1_launch.py; exec bash'"

sleep 2

# Cửa sổ 2: Server cầu nối Wi-Fi phát dữ liệu sang Desktop & MIT App
tmux new-window -t agv_lidar:1 -n bridge \
  "bash -c 'source /opt/ros/jazzy/setup.bash && python3 /home/khangho/rplidar_c1_test/bridge/lidar_bridge_server.py --port 8080; exec bash'"

echo "✅ ĐÃ KHỞI ĐỘNG THÀNH CÔNG HỆ THỐNG TRONG TMUX SESSION [agv_lidar]!"
echo " * LiDAR C1 đang quay quét laser thật..."
echo " * Server đang phát qua Wi-Fi cổng 8080..."

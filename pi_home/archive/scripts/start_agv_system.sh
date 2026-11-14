#!/usr/bin/env bash
source /opt/ros/jazzy/setup.bash
source /home/khangho/rplidar_c1_ws/install/setup.bash

pkill -9 -f 'sllidar_node' 2>/dev/null
pkill -9 -f 'async_slam_toolbox_node' 2>/dev/null
pkill -9 -f 'agv_unified_brain.py' 2>/dev/null
sleep 1

mkdir -p /home/khangho/rplidar_c1_test/logs

echo 1. Khoi dong RPLIDAR C1...
nohup ros2 launch sllidar_ros2 sllidar_c1_launch.py serial_port:=/dev/ttyUSB1 > /home/khangho/rplidar_c1_test/logs/lidar.log 2>&1 &

echo 2. Khoi dong SLAM Toolbox...
nohup ros2 launch slam_toolbox online_async_launch.py > /home/khangho/rplidar_c1_test/logs/slam.log 2>&1 &

echo 3. Khoi dong AGV Unified Brain...
nohup python3 /home/khangho/rplidar_c1_test/bridge/agv_unified_brain.py > /home/khangho/rplidar_c1_test/logs/unified.log 2>&1 &

sleep 3
echo DONE_START

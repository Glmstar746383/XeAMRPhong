#!/bin/bash
# ==============================================================================
# start_bridge.sh - Khởi chạy LiDAR Web Bridge Server trên Raspberry Pi
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BRIDGE_SCRIPT="$ROOT_DIR/bridge/lidar_bridge_server.py"

echo "================================================================="
echo "  KHỞI ĐỘNG RPLIDAR C1M1 WEB & MIT APP BRIDGE SERVER"
echo "================================================================="

# Nạp môi trường ROS 2 nếu có
if [ -f "/opt/ros/jazzy/setup.bash" ]; then
    source /opt/ros/jazzy/setup.bash
    echo "[OK] Đã nạp ROS 2 Jazzy environment."
fi

# Chạy server
python3 "$BRIDGE_SCRIPT" --port 8080 "$@"

#!/usr/bin/env bash
# ==============================================================================
# run_gui.sh - Khởi động GUI Test Tool với môi trường ROS 2 đầy đủ
# Đảm bảo source môi trường và ghi nhận lỗi vào logs/gui.log nếu có sự cố
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
GUI_LOG="$LOG_DIR/gui.log"

mkdir -p "$LOG_DIR"

echo "=== KHỞI ĐỘNG RPLIDAR C1 TEST GUI ===" >> "$GUI_LOG"
echo "Thời gian: $(date)" >> "$GUI_LOG"

# 1. Tự động tìm DISPLAY nếu chưa được gán
if [[ -z "$DISPLAY" ]]; then
    if [[ -S "/tmp/.X11-unix/X0" ]]; then
        export DISPLAY=":0"
    elif [[ -S "/tmp/.X11-unix/X1" ]]; then
        export DISPLAY=":1"
    else
        export DISPLAY=":0"
    fi
fi
echo "Sử dụng DISPLAY=$DISPLAY" >> "$GUI_LOG"

# 2. Nạp môi trường ROS 2
if [[ -f "/opt/ros/jazzy/setup.bash" ]]; then
    source /opt/ros/jazzy/setup.bash
elif [[ -f "/opt/ros/humble/setup.bash" ]]; then
    source /opt/ros/humble/setup.bash
fi

# 3. Nạp workspace chứa package sllidar_ros2
for ws in "$HOME/rplidar_c1_ws" "$HOME/robot_ws"; do
    if [[ -f "$ws/install/setup.bash" ]]; then
        source "$ws/install/setup.bash"
        break
    fi
done

# 4. Khởi chạy ứng dụng Python
cd "$ROOT_DIR"
python3 "$ROOT_DIR/app/main.py" >> "$GUI_LOG" 2>&1

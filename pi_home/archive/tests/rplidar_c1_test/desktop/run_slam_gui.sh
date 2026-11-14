#!/usr/bin/env bash
# ==============================================================================
# run_slam_gui.sh - Khởi chạy SLAM CONTROL GUI với môi trường ROS 2
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
GUI_LOG="$LOG_DIR/slam_gui.log"

mkdir -p "$LOG_DIR"

echo "=== KHỞI ĐỘNG RPLIDAR C1 SLAM GUI ===" >> "$GUI_LOG"
echo "Thời gian: $(date)" >> "$GUI_LOG"

# 1. Tự động tìm DISPLAY
if [[ -z "$DISPLAY" ]]; then
    if [[ -S "/tmp/.X11-unix/X0" ]]; then
        export DISPLAY=":0"
    elif [[ -S "/tmp/.X11-unix/X10" ]]; then
        export DISPLAY=":10"
    elif [[ -S "/tmp/.X11-unix/X1" ]]; then
        export DISPLAY=":1"
    else
        export DISPLAY=":0"
    fi
fi

# 2. Nạp ROS 2
if [[ -f "/opt/ros/jazzy/setup.bash" ]]; then
    source /opt/ros/jazzy/setup.bash
fi
for ws in "$HOME/rplidar_c1_ws" "$HOME/robot_ws"; do
    if [[ -f "$ws/install/setup.bash" ]]; then
        source "$ws/install/setup.bash"
        break
    fi
done

cd "$ROOT_DIR"
python3 "$ROOT_DIR/app/slam_gui.py" >> "$GUI_LOG" 2>&1

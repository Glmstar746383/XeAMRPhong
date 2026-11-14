#!/usr/bin/env bash
# ==============================================================================
# stop_slam.sh - Dừng an toàn SLAM Toolbox và dọn dẹp các node biến đổi TF
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$LOG_DIR/slam.pid"

echo "=================================================="
echo "              DỪNG SLAM TOOLBOX                   "
echo "=================================================="

STOPPED=0

if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "  -> Gửi tín hiệu ngắt đến PID: $PID..."
        kill -SIGINT "$PID" 2>/dev/null || true
        for i in {1..5}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                break
            fi
            sleep 0.5
        done
        if ps -p "$PID" > /dev/null 2>&1; then
            kill -SIGTERM "$PID" 2>/dev/null || true
        fi
        STOPPED=1
    fi
    rm -f "$PID_FILE"
fi

# Dọn dẹp tiến trình async_slam_toolbox_node, odom_tf_broadcaster hoặc static_transform_publisher nếu còn
PIDS=$(pgrep -f "async_slam_toolbox_node|slam_toolbox|odom_tf_broadcaster|static_transform_publisher|static_base_to_laser" || true)
if [[ -n "$PIDS" ]]; then
    echo "  -> Đang dừng các tiến trình liên quan: $PIDS..."
    kill -SIGINT $PIDS 2>/dev/null || true
    sleep 1
    kill -9 $PIDS 2>/dev/null || true
    STOPPED=1
fi

if [[ $STOPPED -eq 1 ]]; then
    echo "[PASS] Đã dừng thành công SLAM Toolbox."
else
    echo "[INFO] Không có tiến trình SLAM Toolbox nào đang chạy."
fi
echo "=================================================="

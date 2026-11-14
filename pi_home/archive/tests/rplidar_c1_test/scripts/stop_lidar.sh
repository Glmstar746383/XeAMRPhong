#!/usr/bin/env bash
# ==============================================================================
# stop_lidar.sh - Dừng an toàn driver RPLIDAR C1 và tắt motor
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$LOG_DIR/lidar.pid"

echo "=================================================="
echo "             DỪNG DRIVER RPLIDAR C1               "
echo "=================================================="

STOPPED=0

# 1. Dừng theo PID file nếu có
if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "  -> Gửi tín hiệu dừng (SIGINT) đến PID: $PID..."
        kill -SIGINT "$PID" 2>/dev/null || true
        # Chờ tiến trình dừng gọn gàng
        for i in {1..5}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                break
            fi
            sleep 0.5
        done
        # Nếu vẫn còn sống, gửi SIGTERM
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "  -> Gửi tín hiệu buộc dừng (SIGTERM)..."
            kill -SIGTERM "$PID" 2>/dev/null || true
        fi
        STOPPED=1
    fi
    rm -f "$PID_FILE"
fi

# 2. Dọn dẹp bất kỳ tiến trình sllidar_node nào còn sót lại
PIDS=$(pgrep -f "sllidar_node" || true)
if [[ -n "$PIDS" ]]; then
    echo "  -> Phát hiện tiến trình sllidar_node tồn đọng: $PIDS. Đang dừng..."
    kill -SIGINT $PIDS 2>/dev/null || true
    sleep 1
    kill -9 $PIDS 2>/dev/null || true
    STOPPED=1
fi

if [[ $STOPPED -eq 1 ]]; then
    echo "[PASS] Đã dừng thành công driver RPLIDAR C1. Motor đã dừng quay."
else
    echo "[INFO] Không có tiến trình driver nào đang chạy."
fi
echo "=================================================="

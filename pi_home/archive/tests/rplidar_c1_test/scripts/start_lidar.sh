#!/usr/bin/env bash
# ==============================================================================
# start_lidar.sh - Khởi động driver RPLIDAR C1 trong nền và lưu log
# Tự động phát hiện cổng serial và nạp đúng môi trường ROS 2
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$LOG_DIR/lidar.pid"
DRIVER_LOG="$LOG_DIR/driver.log"

mkdir -p "$LOG_DIR"

echo "=================================================="
echo "          KHỞI ĐỘNG DRIVER RPLIDAR C1             "
echo "=================================================="

# 1. Kiểm tra xem driver đã đang chạy chưa
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "[WARNING] Driver đã đang chạy với PID: $OLD_PID."
        echo "Nếu muốn khởi động lại, hãy chạy: ./scripts/stop_lidar.sh trước."
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# 2. Nạp môi trường ROS 2
if [[ -z "$ROS_DISTRO" ]]; then
    if [[ -f "/opt/ros/jazzy/setup.bash" ]]; then
        source /opt/ros/jazzy/setup.bash
    elif [[ -f "/opt/ros/humble/setup.bash" ]]; then
        source /opt/ros/humble/setup.bash
    fi
fi

# 3. Nạp workspace chứa package sllidar_ros2
WS_FOUND=0
for ws in "$HOME/rplidar_c1_ws" "$HOME/robot_ws"; do
    if [[ -f "$ws/install/setup.bash" ]]; then
        source "$ws/install/setup.bash"
        WS_FOUND=1
        break
    fi
done

if [[ $WS_FOUND -eq 0 ]] && ! ros2 pkg prefix sllidar_ros2 >/dev/null 2>&1; then
    echo "[FAIL] Không tìm thấy package sllidar_ros2! Vui lòng chạy ./scripts/install_dependencies.sh trước."
    exit 1
fi

# 4. Tự động phát hiện cổng Serial của C1
PORT=$("$SCRIPT_DIR/detect_lidar.sh" --port-only 2>/dev/null || true)
if [[ -z "$PORT" ]]; then
    if [[ -e "/dev/rplidar_c1" ]]; then
        PORT="/dev/rplidar_c1"
    elif [[ -e "/dev/ttyUSB0" ]]; then
        PORT="/dev/ttyUSB0"
    else
        echo "[FAIL] Không tìm thấy cổng kết nối của RPLIDAR C1!"
        echo "Hãy kiểm tra lại cáp USB kết nối giữa cảm biến và Raspberry Pi."
        exit 1
    fi
fi

echo "  -> Cổng Serial phát hiện được: $PORT"
echo "  -> Tốc độ truyền (Baudrate)  : 460800"
echo "  -> Ghi log tại               : $DRIVER_LOG"

# 5. Khởi chạy driver bằng launch file
LAUNCH_FILE="$ROOT_DIR/launch/lidar_test.launch.py"

# Chạy ngầm và chuyển hướng toàn bộ output vào driver.log
nohup ros2 launch "$LAUNCH_FILE" serial_port:="$PORT" serial_baudrate:=460800 > "$DRIVER_LOG" 2>&1 &
DRIVER_PID=$!
echo "$DRIVER_PID" > "$PID_FILE"

echo "  -> Đã kích hoạt tiến trình PID: $DRIVER_PID"

# 6. Đợi 3 giây và kiểm tra xem driver có sống sót không
sleep 3
if ps -p "$DRIVER_PID" > /dev/null 2>&1; then
    echo "[PASS] Driver RPLIDAR C1 đã khởi động thành công!"
    echo "  Để dừng driver, hãy chạy: ./scripts/stop_lidar.sh"
    echo "  Để kiểm tra dữ liệu scan: ./scripts/test_scan.sh"
    echo "=================================================="
    exit 0
else
    echo "[FAIL] Driver bị dừng đột ngột sau khi khởi động!"
    echo "Đoạn log lỗi cuối cùng:"
    tail -n 15 "$DRIVER_LOG"
    rm -f "$PID_FILE"
    echo "=================================================="
    exit 1
fi

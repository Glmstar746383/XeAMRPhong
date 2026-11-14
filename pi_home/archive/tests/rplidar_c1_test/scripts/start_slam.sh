#!/usr/bin/env bash
# ==============================================================================
# start_slam.sh - Khởi động SLAM Toolbox và kiểm tra xuất bản /map
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$LOG_DIR/slam.pid"
SLAM_LOG="$LOG_DIR/slam_toolbox.log"

mkdir -p "$LOG_DIR"

echo "=================================================="
echo "           KHỞI ĐỘNG SLAM TOOLBOX                 "
echo "=================================================="

# 1. Kiểm tra xem SLAM Toolbox đã đang chạy chưa
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "[WARNING] SLAM Toolbox đã đang chạy với PID: $OLD_PID."
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
for ws in "$HOME/rplidar_c1_ws" "$HOME/robot_ws"; do
    if [[ -f "$ws/install/setup.bash" ]]; then
        source "$ws/install/setup.bash"
    fi
done

# 3. Đảm bảo cảm biến RPLIDAR C1 đã được khởi động
if ! ros2 topic list 2>/dev/null | grep -q "^/scan$"; then
    echo "  -> Topic /scan chưa có. Đang tự động bật RPLIDAR C1..."
    "$SCRIPT_DIR/start_lidar.sh"
    sleep 2
fi

# 4. Khởi chạy SLAM Toolbox
LAUNCH_FILE="$ROOT_DIR/launch/slam_mapping.launch.py"
echo "  -> File Launch       : $LAUNCH_FILE"
echo "  -> Nhật ký ghi tại   : $SLAM_LOG"

nohup ros2 launch "$LAUNCH_FILE" > "$SLAM_LOG" 2>&1 &
SLAM_PID=$!
echo "$SLAM_PID" > "$PID_FILE"
echo "  -> Đã kích hoạt tiến trình SLAM Toolbox PID: $SLAM_PID"

# 5. Tự động kích hoạt Lifecycle Node cho slam_toolbox
echo "  -> Đang cấu hình và kích hoạt Lifecycle Node /slam_toolbox..."
for i in {1..8}; do
    sleep 1
    if ros2 lifecycle get /slam_toolbox 2>/dev/null | grep -q "unconfigured"; then
        ros2 lifecycle set /slam_toolbox configure >/dev/null 2>&1 || true
        sleep 1
        ros2 lifecycle set /slam_toolbox activate >/dev/null 2>&1 || true
        break
    elif ros2 lifecycle get /slam_toolbox 2>/dev/null | grep -q "inactive"; then
        ros2 lifecycle set /slam_toolbox activate >/dev/null 2>&1 || true
        break
    fi
done

# 6. Kiểm tra topic /map
echo "  -> Đang kiểm tra xuất bản /map..."
MAP_FOUND=0
for i in {1..8}; do
    sleep 1
    if ros2 topic list 2>/dev/null | grep -q "^/map$"; then
        MAP_FOUND=1
        break
    fi
done

if [[ $MAP_FOUND -eq 1 ]]; then
    echo "[PASS] SLAM Toolbox đã khởi động thành công! Topic /map đang hoạt động."
    echo "  Để xem bản đồ realtime: Hãy bấm [ VIEW MAP ] trên GUI hoặc chạy RViz2."
    echo "  Để lưu bản đồ         : Chạy ./scripts/save_map.sh"
    echo "  Để dừng SLAM          : Chạy ./scripts/stop_slam.sh"
    echo "=================================================="
    exit 0
else
    echo "[FAIL] Chưa thấy topic /map xuất hiện sau 12 giây khởi động!"
    echo "Đoạn log cuối cùng của SLAM Toolbox:"
    tail -n 15 "$SLAM_LOG"
    echo "=================================================="
    exit 1
fi

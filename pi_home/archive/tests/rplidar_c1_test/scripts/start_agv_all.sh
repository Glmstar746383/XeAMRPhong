#!/usr/bin/env bash
# ==============================================================================
# start_agv_all.sh - Khởi động đồng thời cả Driver LiDAR C1 và Server truyền Wi-Fi
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "================================================================="
echo "   🚀 KHỞI ĐỘNG HỆ THỐNG QUÉT LASER VÀ TRUYỀN DỮ LIỆU AGV"
echo "================================================================="

# 1. Nạp môi trường ROS 2 Jazzy hoặc Humble
if [ -f "/opt/ros/jazzy/setup.bash" ]; then
    source /opt/ros/jazzy/setup.bash
    echo "[OK] Nạp ROS 2 Jazzy."
elif [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
    echo "[OK] Nạp ROS 2 Humble."
fi

# 2. Nạp workspace chứa driver sllidar_ros2
for ws in "$HOME/rplidar_c1_ws" "$HOME/robot_ws" "$ROOT_DIR"; do
    if [ -f "$ws/install/setup.bash" ]; then
        source "$ws/install/setup.bash"
        echo "[OK] Nạp workspace: $ws"
        break
    fi
done

# Hàm xử lý khi bấm Ctrl+C để dừng sạch cả 2 tiến trình
cleanup() {
    echo ""
    echo "[STOP] Đang dừng toàn bộ hệ thống..."
    kill $(jobs -p) 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "-> Bước 1: Khởi động Driver RPLIDAR C1M1 quét laser thật..."
ros2 launch sllidar_ros2 sllidar_c1_launch.py &
LIDAR_PID=$!
sleep 2

echo "-> Bước 2: Khởi động Server truyền sóng Wi-Fi tới Desktop & MIT App..."
python3 "$ROOT_DIR/bridge/lidar_bridge_server.py" --port 8080 &
BRIDGE_PID=$!

IP_ADDR=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$IP_ADDR" ]; then IP_ADDR="127.0.0.1"; fi

echo ""
echo "================================================================="
echo " ✅ HỆ THỐNG ĐÃ HOẠT ĐỘNG HOÀN TOÀN TỰ ĐỘNG KHÔNG DÂY (WI-FI)!"
echo "================================================================="
echo " 🌐 Địa chỉ IP của Pi : $IP_ADDR"
echo " 🖥️ Trên Máy tính Desktop : Mở trình duyệt gõ: http://$IP_ADDR:8080/"
echo "                          (hoặc http://khang.local:8080/)"
echo " 📱 Trên Điện thoại App   : Mở http://$IP_ADDR:8080/radar"
echo "                          (hoặc API: http://$IP_ADDR:8080/api/zones)"
echo " Nhấn [Ctrl + C] để dừng toàn bộ."
echo "================================================================="

# Chờ các tiến trình
wait

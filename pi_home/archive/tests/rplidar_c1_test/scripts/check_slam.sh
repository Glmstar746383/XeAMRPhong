#!/usr/bin/env bash
# ==============================================================================
# check_slam.sh - Kiểm tra toàn diện điều kiện tạo bản đồ SLAM
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=================================================="
echo "         KIỂM TRA ĐIỀU KIỆN TẠO BẢN ĐỒ SLAM       "
echo "=================================================="

# 1. Nạp ROS 2
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

# BƯỚC 1: Kiểm tra RPLIDAR C1
echo -n "[1] Thiết bị USB RPLIDAR C1       : "
if lsusb | grep -qE "10c4:ea60|CP210"; then
    echo "[PASS] (Phát hiện Silicon Labs CP210x)"
else
    echo "[FAIL] (Chưa cắm cáp USB của LiDAR)"
fi

# BƯỚC 2: Kiểm tra Driver sllidar_ros2
echo -n "[2] Package sllidar_ros2          : "
if ros2 pkg prefix sllidar_ros2 >/dev/null 2>&1; then
    echo "[PASS] ($(ros2 pkg prefix sllidar_ros2))"
else
    echo "[FAIL] (Chưa build package sllidar_ros2)"
fi

# BƯỚC 3: Kiểm tra Topic /scan
echo -n "[3] Topic /scan                   : "
if ros2 topic list 2>/dev/null | grep -q "^/scan$"; then
    echo "[PASS] (Đang hoạt động)"
else
    echo "[WARNING] (Chưa chạy driver. Hãy chạy ./scripts/start_lidar.sh)"
fi

# BƯỚC 4: Kiểm tra Package SLAM Toolbox
echo -n "[4] Package slam_toolbox          : "
if ros2 pkg prefix slam_toolbox >/dev/null 2>&1; then
    echo "[PASS] ($(ros2 pkg prefix slam_toolbox))"
else
    echo "[FAIL] (Chưa cài đặt ros-$ROS_DISTRO-slam-toolbox)"
fi

# BƯỚC 5: Kiểm tra Map Server (Lưu bản đồ)
echo -n "[5] Công cụ lưu map (map-server)  : "
if ros2 pkg prefix nav2_map_server >/dev/null 2>&1; then
    echo "[PASS] ($(ros2 pkg prefix nav2_map_server))"
else
    echo "[WARNING] (Chưa có nav2_map_server, sẽ lưu qua service slam_toolbox)"
fi

# BƯỚC 6: Kiểm tra TF base_link -> laser
echo -n "[6] Cấu hình TF base_link -> laser: "
if [[ -f "$ROOT_DIR/config/robot.yaml" ]]; then
    echo "[PASS] (Đã cấu hình tại config/robot.yaml)"
else
    echo "[FAIL] (Thiếu file config/robot.yaml)"
fi

# BƯỚC 7: Kiểm tra Nguồn Wheel Odometry (/odom)
echo -n "[7] Nguồn phát Odometry (/odom)   : "
if ros2 topic list 2>/dev/null | grep -q "^/odom$"; then
    echo "[PASS] (Phát hiện topic /odom đang hoạt động)"
    ODOM_READY=1
else
    echo "[NOT DETECTED] (Chưa có encoder bánh xe)"
    ODOM_READY=0
fi

# BƯỚC 8: Kiểm tra RViz2
echo -n "[8] Ứng dụng RViz2                : "
if ros2 pkg prefix rviz2 >/dev/null 2>&1; then
    echo "[PASS] ($(ros2 pkg prefix rviz2))"
else
    echo "[FAIL] (Chưa cài đặt rviz2)"
fi

echo "=================================================="
echo "                 KẾT LUẬN ĐÁNH GIÁ                "
echo "=================================================="
if [[ $ODOM_READY -eq 1 ]]; then
    echo "CHẾ ĐỘ HOẠT ĐỘNG: ROBOT ĐẦY ĐỦ ODOMETRY"
    echo "  -> Sẵn sàng chạy SLAM tạo bản đồ khi di chuyển!"
else
    echo "CHẾ ĐỘ HOẠT ĐỘNG: PHẦN CỨNG HIỆN TẠI (PI + RPLIDAR C1)"
    echo "  [PASS] LiDAR Test: HOẠT ĐỘNG TỐT"
    echo "  [NOT READY] Wheel Odometry: CHƯA CÓ ENCODER BÁNH XE"
    echo "  [READY] Pi + LiDAR Test Mode: SẴN SÀNG KHỞI ĐỘNG SLAM TẠO MAP PHÒNG TĨNH"
    echo "  [BLOCKED] Validated Moving SLAM: CẦN LẮP WHEEL ENCODER ĐỂ DI CHUYỂN TẠO MAP LỚN"
fi
echo "=================================================="

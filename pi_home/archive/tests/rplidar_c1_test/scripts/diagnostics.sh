#!/usr/bin/env bash
# ==============================================================================
# diagnostics.sh - Báo cáo chẩn đoán toàn diện hệ thống và cảm biến RPLIDAR C1
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
DIAG_LOG="$LOG_DIR/diagnostics.log"

mkdir -p "$LOG_DIR"

exec > >(tee "$DIAG_LOG") 2>&1

echo "=================================================="
echo "    BÁO CÁO CHẨN ĐOÁN HỆ THỐNG RPLIDAR C1 TEST   "
echo "    Thời gian: $(date '+%Y-%m-%d %H:%M:%S')      "
echo "=================================================="

# 1. Hệ điều hành & Kiến trúc
echo -e "\n[1. HỆ ĐIỀU HÀNH & KIẾN TRÚC]"
echo "Host: $(hostname)"
echo "Kernel: $(uname -r)"
echo "Arch: $(uname -m)"
if command -v lsb_release >/dev/null 2>&1; then
    lsb_release -d
fi

# 2. Kiểm tra nguồn điện Raspberry Pi (Undervoltage)
echo -e "\n[2. KIỂM TRA NGUỒN ĐIỆN & NHIỆT ĐỘ]"
if command -v vcgencmd >/dev/null 2>&1; then
    THROTTLE=$(vcgencmd get_throttled || true)
    TEMP=$(vcgencmd measure_temp || true)
    echo "Throttled status : $THROTTLE"
    echo "Core Temperature : $TEMP"
    if [[ "$THROTTLE" == *"0x0"* ]]; then
        echo "-> [PASS] Nguồn điện và nhiệt độ hoàn toàn ổn định."
    else
        echo "-> [WARNING] Phát hiện cảnh báo nguồn/nhiệt: $THROTTLE"
    fi
else
    echo "Kiểm tra dmesg cảnh báo nguồn:"
    sudo -n dmesg 2>/dev/null | grep -iE "under-voltage|throttled" | tail -n 5 || echo "Không có cảnh báo sụt nguồn trong dmesg."
fi

# 3. Môi trường ROS 2
echo -e "\n[3. MÔI TRƯỜNG ROS 2]"
echo "ROS_DISTRO hiện tại: ${ROS_DISTRO:-Chưa nạp}"
for d in /opt/ros/*; do
    if [[ -d "$d" ]]; then
        echo "Tìm thấy ROS 2 tại: $d"
    fi
done

# 4. Kiểm tra Workspace & Driver sllidar_ros2
echo -e "\n[4. PACKAGE DRIVER SLLIDAR_ROS2]"
source /opt/ros/jazzy/setup.bash 2>/dev/null || source /opt/ros/humble/setup.bash 2>/dev/null || true
for ws in "$HOME/rplidar_c1_ws" "$HOME/robot_ws"; do
    if [[ -f "$ws/install/setup.bash" ]]; then
        source "$ws/install/setup.bash"
        echo "Đã nạp workspace: $ws"
    fi
done

if ros2 pkg prefix sllidar_ros2 >/dev/null 2>&1; then
    echo "[PASS] Package sllidar_ros2: $(ros2 pkg prefix sllidar_ros2)"
else
    echo "[FAIL] Package sllidar_ros2 chưa được cài đặt hoặc chưa source workspace!"
fi

# 5. Kiểm tra RViz2
echo -e "\n[5. KIỂM TRA RVIZ2]"
if ros2 pkg prefix rviz2 >/dev/null 2>&1; then
    echo "[PASS] RViz2 đã được cài đặt: $(ros2 pkg prefix rviz2)"
else
    echo "[FAIL] Chưa cài đặt rviz2!"
fi

# 6. Thiết bị USB & Cổng Serial
echo -e "\n[6. THIẾT BỊ USB & CỔNG SERIAL]"
echo "Danh sách USB liên quan đến UART/Serial:"
lsusb | grep -iE "CP210|FTDI|CH34|Silicon|UART|Serial" || lsusb

echo -e "\nDanh mục trong /dev/serial/by-id/:"
if [[ -d "/dev/serial/by-id" ]]; then
    ls -la /dev/serial/by-id/
else
    echo "Thư mục /dev/serial/by-id/ không tồn tại."
fi

echo -e "\nKiểm tra symlink /dev/rplidar_c1:"
if [[ -e "/dev/rplidar_c1" ]]; then
    ls -l /dev/rplidar_c1
else
    echo "Chưa có symlink /dev/rplidar_c1."
fi

# 7. Quyền người dùng & Nhóm
echo -e "\n[7. QUYỀN TRUY CẬP SERIAL]"
echo "User: $(whoami)"
echo "Groups: $(groups)"
if groups | grep -q "\bdialout\b"; then
    echo "[PASS] User thuộc nhóm dialout."
else
    echo "[FAIL] User KHÔNG thuộc nhóm dialout!"
fi

# 8. Tiến trình đang chạy
echo -e "\n[8. TIẾN TRÌNH DRIVER & RVIZ]"
pgrep -fl "sllidar_node|rviz2" || echo "Không có tiến trình sllidar_node hoặc rviz2 nào đang chạy."

# 9. Trích xuất Log gần nhất
echo -e "\n[9. NHẬT KÝ LOG GẦN NHẤT]"
if [[ -f "$LOG_DIR/driver.log" ]]; then
    echo "--- 10 dòng cuối của driver.log ---"
    tail -n 10 "$LOG_DIR/driver.log"
fi

echo -e "\n=================================================="
echo "  Báo cáo chẩn đoán đã được lưu tại:"
echo "    $DIAG_LOG"
echo "=================================================="

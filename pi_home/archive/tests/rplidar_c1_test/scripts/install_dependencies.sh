#!/usr/bin/env bash
# ==============================================================================
# install_dependencies.sh - Cài đặt thư viện phụ thuộc và build driver sllidar_ros2
# Nguồn chính thức: https://github.com/Slamtec/sllidar_ros2
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_DIR="${HOME}/rplidar_c1_ws"

echo "=================================================="
echo "    CÀI ĐẶT THƯ VIỆN & BUILD DRIVER SLLIDAR_ROS2  "
echo "=================================================="

# 1. Kiểm tra môi trường ROS 2
if [[ -z "$ROS_DISTRO" ]]; then
    if [[ -f "/opt/ros/jazzy/setup.bash" ]]; then
        source /opt/ros/jazzy/setup.bash
    elif [[ -f "/opt/ros/humble/setup.bash" ]]; then
        source /opt/ros/humble/setup.bash
    elif [[ -f "/opt/ros/iron/setup.bash" ]]; then
        source /opt/ros/iron/setup.bash
    else
        echo "[FAIL] Không tìm thấy ROS 2 trong /opt/ros/! Vui lòng cài đặt ROS 2 trước."
        exit 1
    fi
fi
echo "[BƯỚC 1] Phát hiện ROS 2 Distro: $ROS_DISTRO [PASS]"

# 2. Cài đặt các gói hệ thống cần thiết (python3-tk, colcon, git)
echo "[BƯỚC 2] Kiểm tra và cài đặt gói hệ thống bổ trợ..."
MISSING_PKGS=()
for pkg in python3-tk python3-serial git colcon; do
    if ! dpkg -s "$pkg" &>/dev/null && ! which "$pkg" &>/dev/null; then
        MISSING_PKGS+=("$pkg")
    fi
done

if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
    echo "  -> Đang cài đặt các gói còn thiếu: ${MISSING_PKGS[*]}"
    sudo apt-get update -y
    sudo apt-get install -y python3-tk python3-serial git python3-colcon-common-extensions
else
    echo "  -> Toàn bộ gói phụ trợ đã sẵn sàng. [PASS]"
fi

# 3. Tạo workspace riêng biệt cho sllidar_ros2 để không làm ảnh hưởng môi trường khác
echo "[BƯỚC 3] Thiết lập workspace tại: $WS_DIR"
mkdir -p "$WS_DIR/src"

cd "$WS_DIR/src"
if [[ -d "sllidar_ros2" ]]; then
    echo "  -> Repository sllidar_ros2 đã tồn tại. Đang cập nhật (git pull)..."
    cd sllidar_ros2
    git pull origin main || git pull origin master || true
    cd ..
else
    echo "  -> Clone mã nguồn driver chính hãng từ Slamtec..."
    git clone https://github.com/Slamtec/sllidar_ros2.git
fi

# 4. Biên dịch package sllidar_ros2
echo "[BƯỚC 4] Biên dịch driver bằng colcon..."
cd "$WS_DIR"
colcon build --symlink-install --packages-select sllidar_ros2

# 5. Kiểm tra kết quả biên dịch
echo "[BƯỚC 5] Kiểm tra driver sau khi build..."
source "$WS_DIR/install/setup.bash"
if ros2 pkg prefix sllidar_ros2 &>/dev/null; then
    PREFIX=$(ros2 pkg prefix sllidar_ros2)
    echo "  -> [PASS] Package sllidar_ros2 đã sẵn sàng tại: $PREFIX"
else
    echo "  -> [FAIL] Không tìm thấy package sllidar_ros2 sau khi build!"
    exit 1
fi

echo "=================================================="
echo "          CÀI ĐẶT THÀNH CÔNG HOÀN TOÀN!           "
echo "  Để sử dụng trong terminal khác, hãy chạy:       "
echo "    source $WS_DIR/install/setup.bash             "
echo "=================================================="

#!/usr/bin/env bash
# ==============================================================================
# inspect_tf.sh - Giám sát cây biến đổi tọa độ TF2 (TF Tree Monitor)
# ==============================================================================

set -eo pipefail

if [[ -z "$ROS_DISTRO" ]]; then
    if [[ -f "/opt/ros/jazzy/setup.bash" ]]; then
        source /opt/ros/jazzy/setup.bash
    fi
fi

echo "=================================================="
echo "          GIÁM SÁT CÂY BIẾN ĐỔI TF2 REALTIME      "
echo "=================================================="

# 1. Kiểm tra topic /tf và /tf_static
echo -n "Topic /tf         : "
ros2 topic list 2>/dev/null | grep -q "^/tf$" && echo "[ACTIVE]" || echo "[INACTIVE]"

echo -n "Topic /tf_static  : "
ros2 topic list 2>/dev/null | grep -q "^/tf_static$" && echo "[ACTIVE]" || echo "[INACTIVE]"

echo -e "\n--- Kiểm tra Transform: base_link -> laser ---"
timeout 3s ros2 run tf2_ros tf2_echo base_link laser 2>/dev/null || echo "[WARNING] Không tìm thấy transform base_link -> laser."

echo -e "\n--- Kiểm tra Transform: odom -> base_link ---"
timeout 3s ros2 run tf2_ros tf2_echo odom base_link 2>/dev/null || echo "[WARNING] Không tìm thấy transform odom -> base_link."

echo -e "\n--- Kiểm tra Transform: map -> odom ---"
timeout 3s ros2 run tf2_ros tf2_echo map odom 2>/dev/null || echo "[INFO] map -> odom chỉ xuất hiện khi SLAM Toolbox đang chạy."

echo "=================================================="

#!/usr/bin/env bash
# ==============================================================================
# save_map.sh - Lưu bản đồ 2D dạng chuẩn (.pgm, .yaml, .posegraph) từ SLAM Toolbox
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Nạp ROS 2
if [[ -z "$ROS_DISTRO" ]]; then
    if [[ -f "/opt/ros/jazzy/setup.bash" ]]; then
        source /opt/ros/jazzy/setup.bash
    fi
fi

# Chạy client python lưu bản đồ
python3 "$SCRIPT_DIR/save_map.py" "$@"

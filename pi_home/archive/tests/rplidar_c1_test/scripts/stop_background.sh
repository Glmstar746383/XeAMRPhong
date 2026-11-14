#!/usr/bin/env bash
# ==============================================================================
# stop_background.sh - Dừng toàn bộ hệ thống LiDAR và Bridge
# ==============================================================================

tmux kill-session -t agv_lidar 2>/dev/null || true
pkill -f sllidar_node 2>/dev/null || true
pkill -f lidar_bridge_server.py 2>/dev/null || true

echo "🛑 Đã dừng toàn bộ hệ thống LiDAR và Bridge."

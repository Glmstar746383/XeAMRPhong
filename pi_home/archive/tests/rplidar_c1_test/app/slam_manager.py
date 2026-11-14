#!/usr/bin/env python3
# ==============================================================================
# slam_manager.py - Quản lý tiến trình SLAM Toolbox, RViz2 và bản đồ /map
# ==============================================================================

import os
import subprocess
import threading
import time

class SlamManager:
    def __init__(self, root_dir=None):
        self.root_dir = root_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.log_dir = os.path.join(self.root_dir, "logs")
        self.pid_file = os.path.join(self.log_dir, "slam.pid")
        self.rviz_proc = None
        
        self.lock = threading.Lock()
        self.has_map = False
        self.map_width_m = 0.0
        self.map_height_m = 0.0
        self.map_cells = 0
        self.resolution = 0.05
        self.map_received_count = 0
        self.last_map_time = 0.0
        
        self.stop_event = threading.Event()
        self.map_thread = None

    def start_map_listener(self):
        if self.map_thread and self.map_thread.is_alive():
            return
        self.stop_event.clear()
        self.map_thread = threading.Thread(target=self._map_worker, daemon=True)
        self.map_thread.start()

    def _map_worker(self):
        try:
            import rclpy
            from rclpy.node import Node
            from nav_msgs.msg import OccupancyGrid
            from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
        except ImportError:
            return

        if not rclpy.ok():
            rclpy.init()

        node = Node("gui_map_monitor")
        qos = QoSProfile(
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
            depth=5
        )

        def map_cb(msg):
            with self.lock:
                self.has_map = True
                self.map_received_count += 1
                self.last_map_time = time.time()
                self.resolution = msg.info.resolution
                self.map_width_m = msg.info.width * msg.info.resolution
                self.map_height_m = msg.info.height * msg.info.resolution
                self.map_cells = msg.info.width * msg.info.height

        from rclpy.executors import SingleThreadedExecutor
        sub = node.create_subscription(OccupancyGrid, "/map", map_cb, qos)
        executor = SingleThreadedExecutor()
        executor.add_node(node)

        while not self.stop_event.is_set():
            executor.spin_once(timeout_sec=0.5)

        executor.remove_node(node)
        node.destroy_node()

    def is_running(self):
        # 1. Kiểm tra PID file
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)
                return True
            except (OSError, ValueError):
                pass
        
        # 2. Kiểm tra tiến trình async_slam_toolbox_node
        try:
            res = subprocess.run(["pgrep", "-f", "async_slam_toolbox_node"], stdout=subprocess.PIPE, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return True
        except Exception:
            pass
        return False

    def start_slam(self):
        start_script = os.path.join(self.root_dir, "scripts", "start_slam.sh")
        try:
            res = subprocess.run(
                ["bash", start_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=20
            )
            return res.returncode == 0, res.stdout or res.stderr
        except Exception as e:
            return False, f"Ngoại lệ khi gọi start_slam.sh: {e}"

    def stop_slam(self):
        stop_script = os.path.join(self.root_dir, "scripts", "stop_slam.sh")
        try:
            res = subprocess.run(
                ["bash", stop_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            return True, res.stdout
        except Exception as e:
            return False, f"Ngoại lệ khi gọi stop_slam.sh: {e}"

    def start_rviz(self):
        if self.rviz_proc and self.rviz_proc.poll() is None:
            return True, "RViz2 đã đang mở."

        rviz_config = os.path.join(self.root_dir, "config", "slam.rviz")
        ros_distro = os.environ.get("ROS_DISTRO", "jazzy")
        cmd = f"source /opt/ros/{ros_distro}/setup.bash 2>/dev/null; rviz2 -d '{rviz_config}'"
        
        try:
            self.rviz_proc = subprocess.Popen(
                ["bash", "-l", "-c", cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return True, "Đã mở RViz2 với cấu hình SLAM."
        except Exception as e:
            return False, f"Không thể mở RViz2: {e}"

    def save_map(self, map_name=None):
        save_script = os.path.join(self.root_dir, "scripts", "save_map.sh")
        cmd = ["bash", save_script]
        if map_name:
            cmd.append(map_name)
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            return res.returncode == 0, res.stdout or res.stderr
        except Exception as e:
            return False, f"Lỗi khi lưu bản đồ: {e}"

    def reset_map(self):
        # Gọi service reset của SLAM Toolbox nếu có
        cmd = "source /opt/ros/jazzy/setup.bash 2>/dev/null; ros2 service call /slam_toolbox/reset slam_toolbox/srv/Reset {}"
        try:
            subprocess.run(["bash", "-c", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            with self.lock:
                self.has_map = False
                self.map_width_m = 0.0
                self.map_height_m = 0.0
                self.map_cells = 0
            return True, "Đã gửi lệnh Reset phiên bản đồ hiện tại."
        except Exception as e:
            return False, f"Lỗi khi reset map: {e}"

    def get_map_stats(self):
        with self.lock:
            active = self.has_map and (time.time() - self.last_map_time < 5.0) if self.last_map_time > 0 else self.has_map
            return {
                "active": active,
                "width_m": self.map_width_m,
                "height_m": self.map_height_m,
                "cells": self.map_cells,
                "resolution": self.resolution,
                "count": self.map_received_count
            }

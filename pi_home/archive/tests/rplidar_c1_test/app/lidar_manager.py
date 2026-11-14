#!/usr/bin/env python3
# ==============================================================================
# lidar_manager.py - Quản lý vòng đời tiến trình Driver RPLIDAR C1
# ==============================================================================

import os
import signal
import subprocess
import time

class LidarManager:
    def __init__(self, root_dir=None):
        self.root_dir = root_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.log_dir = os.path.join(self.root_dir, "logs")
        self.pid_file = os.path.join(self.log_dir, "lidar.pid")
        self.driver_log = os.path.join(self.log_dir, "driver.log")
        self.rviz_proc = None

    def is_running(self):
        # 1. Kiểm tra PID file
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, "r") as f:
                    pid = int(f.read().strip())
                # Gửi tín hiệu 0 để kiểm tra tiến trình có tồn tại không
                os.kill(pid, 0)
                return True
            except (OSError, ValueError):
                pass
        
        # 2. Kiểm tra tiến trình sllidar_node
        try:
            res = subprocess.run(["pgrep", "-f", "sllidar_node"], stdout=subprocess.PIPE, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return True
        except Exception:
            pass
        return False

    def start_lidar(self):
        if self.is_running():
            return True, "Driver đã đang chạy."
        
        start_script = os.path.join(self.root_dir, "scripts", "start_lidar.sh")
        try:
            res = subprocess.run(
                ["bash", start_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15
            )
            if res.returncode == 0:
                return True, res.stdout
            else:
                return False, f"Lỗi khởi động:\n{res.stderr or res.stdout}"
        except Exception as e:
            return False, f"Ngoại lệ khi gọi start_lidar.sh: {str(e)}"

    def stop_lidar(self):
        stop_script = os.path.join(self.root_dir, "scripts", "stop_lidar.sh")
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
            return False, f"Ngoại lệ khi dừng driver: {str(e)}"

    def start_rviz(self):
        if self.rviz_proc and self.rviz_proc.poll() is None:
            return True, "RViz2 đã đang mở."

        rviz_config = os.path.join(self.root_dir, "config", "rplidar_c1.rviz")
        ros_distro = os.environ.get("ROS_DISTRO", "jazzy")
        cmd = f"source /opt/ros/{ros_distro}/setup.bash 2>/dev/null; rviz2 -d '{rviz_config}'"
        
        try:
            self.rviz_proc = subprocess.Popen(
                ["bash", "-l", "-c", cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return True, "Đã mở RViz2."
        except Exception as e:
            return False, f"Không thể mở RViz2: {str(e)}"

    def stop_rviz(self):
        if self.rviz_proc and self.rviz_proc.poll() is None:
            try:
                self.rviz_proc.terminate()
                self.rviz_proc.wait(timeout=2)
            except Exception:
                self.rviz_proc.kill()
            self.rviz_proc = None
        subprocess.run(["pkill", "-f", "rviz2"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, "Đã đóng RViz2."

    def get_last_driver_logs(self, lines=20):
        if os.path.exists(self.driver_log):
            try:
                with open(self.driver_log, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
                    return "".join(all_lines[-lines:])
            except Exception as e:
                return f"Lỗi đọc log: {e}"
        return "Chưa có file driver.log"

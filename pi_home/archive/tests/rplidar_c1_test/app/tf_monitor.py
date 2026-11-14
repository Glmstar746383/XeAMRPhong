#!/usr/bin/env python3
# ==============================================================================
# tf_monitor.py - Giám sát cây biến đổi tọa độ TF2
# ==============================================================================

import subprocess
import time

class TfMonitor:
    def __init__(self):
        pass

    def check_transform(self, parent, child, timeout=2.0):
        cmd = ["ros2", "run", "tf2_ros", "tf2_echo", parent, child]
        try:
            res = subprocess.run(
                ["bash", "-c", f"source /opt/ros/jazzy/setup.bash 2>/dev/null; {' '.join(cmd)}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            if "Translation:" in res.stdout or "Rotation:" in res.stdout:
                return True, "Transform hợp lệ"
            return False, "Không tìm thấy transform"
        except subprocess.TimeoutExpired:
            return False, "Hết thời gian chờ (Timeout)"
        except Exception as e:
            return False, str(e)

    def get_tf_status(self):
        # Kiểm tra nhanh 2 liên kết trọng yếu
        has_base_laser, _ = self.check_transform("base_link", "laser", timeout=1.5)
        has_odom_base, _ = self.check_transform("odom", "base_link", timeout=1.5)
        has_map_odom, _ = self.check_transform("map", "odom", timeout=1.5)
        
        return {
            "base_link_to_laser": has_base_laser,
            "odom_to_base_link": has_odom_base,
            "map_to_odom": has_map_odom,
            "tree_ready": has_base_laser and has_odom_base
        }

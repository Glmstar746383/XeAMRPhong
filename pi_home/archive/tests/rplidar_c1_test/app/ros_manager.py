#!/usr/bin/env python3
# ==============================================================================
# ros_manager.py - Subscriber theo dõi dữ liệu /scan realtime cho GUI
# ==============================================================================

import time
import math
import threading
from collections import deque

class RosManager:
    def __init__(self):
        self.is_active = False
        self.lock = threading.Lock()
        
        # Thống kê realtime
        self.scan_count = 0
        self.hz = 0.0
        self.valid_points = 0
        self.total_points = 0
        self.valid_ratio = 0.0
        self.min_dist = 0.0
        self.max_dist = 0.0
        self.angle_min_deg = 0.0
        self.angle_max_deg = 0.0
        self.last_msg_time = 0.0
        self.is_receiving = False
        
        self.timestamps = deque(maxlen=20)
        self.thread = None
        self.stop_event = threading.Event()

    def start_monitoring(self):
        if self.is_active:
            return
        self.is_active = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop_monitoring(self):
        self.stop_event.set()
        self.is_active = False

    def _worker(self):
        # Cố gắng import rclpy
        try:
            import rclpy
            from rclpy.node import Node
            from sensor_msgs.msg import LaserScan
            from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
        except ImportError:
            # Fallback nếu rclpy không có sẵn trong context
            self._fallback_worker()
            return

        if not rclpy.ok():
            rclpy.init()

        node = Node("gui_scan_monitor")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        def callback(msg):
            now = time.time()
            with self.lock:
                self.scan_count += 1
                self.last_msg_time = now
                self.timestamps.append(now)
                
                # Tính tần số Hz từ rolling timestamps
                if len(self.timestamps) > 1:
                    dt = self.timestamps[-1] - self.timestamps[0]
                    if dt > 0:
                        self.hz = (len(self.timestamps) - 1) / dt
                
                self.total_points = len(msg.ranges)
                valid_pts = 0
                min_d = float('inf')
                max_d = 0.0
                
                for r in msg.ranges:
                    if math.isfinite(r) and msg.range_min <= r <= msg.range_max:
                        valid_pts += 1
                        if r < min_d:
                            min_d = r
                        if r > max_d:
                            max_d = r
                            
                self.valid_points = valid_pts
                self.valid_ratio = (valid_pts / self.total_points * 100) if self.total_points > 0 else 0.0
                self.min_dist = min_d if min_d != float('inf') else 0.0
                self.max_dist = max_d
                self.angle_min_deg = math.degrees(msg.angle_min)
                self.angle_max_deg = math.degrees(msg.angle_max)

        from rclpy.executors import SingleThreadedExecutor
        sub = node.create_subscription(LaserScan, "/scan", callback, qos)
        executor = SingleThreadedExecutor()
        executor.add_node(node)

        while not self.stop_event.is_set():
            executor.spin_once(timeout_sec=0.2)
            with self.lock:
                # Nếu quá 2.0s không có tin nhắn mới -> coi như mất tín hiệu
                self.is_receiving = (time.time() - self.last_msg_time < 2.0) and (self.scan_count > 0)

        executor.remove_node(node)
        node.destroy_node()

    def _fallback_worker(self):
        # Fallback loop kiểm tra định kỳ nếu không có rclpy trực tiếp
        while not self.stop_event.is_set():
            time.sleep(0.5)

    def get_stats(self):
        with self.lock:
            # Kiểm tra xem có đang nhận dữ liệu không
            receiving = (time.time() - self.last_msg_time < 2.0) if self.last_msg_time > 0 else False
            return {
                "receiving": receiving,
                "scan_count": self.scan_count,
                "hz": self.hz if receiving else 0.0,
                "valid_points": self.valid_points if receiving else 0,
                "total_points": self.total_points if receiving else 0,
                "valid_ratio": self.valid_ratio if receiving else 0.0,
                "min_dist": self.min_dist if receiving else 0.0,
                "max_dist": self.max_dist if receiving else 0.0,
                "angle_min_deg": self.angle_min_deg,
                "angle_max_deg": self.angle_max_deg
            }

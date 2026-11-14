#!/usr/bin/env python3
# ==============================================================================
# odom_monitor.py - Giám sát luồng dữ liệu Odometry trên topic /odom
# ==============================================================================

import time
import threading
from collections import deque

class OdomMonitor:
    def __init__(self):
        self.is_active = False
        self.lock = threading.Lock()
        self.has_odom = False
        self.odom_count = 0
        self.hz = 0.0
        self.last_msg_time = 0.0
        self.vx = 0.0
        self.vtheta = 0.0
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
        try:
            import rclpy
            from rclpy.node import Node
            from nav_msgs.msg import Odometry
            from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
        except ImportError:
            return

        if not rclpy.ok():
            rclpy.init()

        node = Node("gui_odom_monitor")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        def cb(msg):
            now = time.time()
            with self.lock:
                self.has_odom = True
                self.odom_count += 1
                self.last_msg_time = now
                self.timestamps.append(now)
                if len(self.timestamps) > 1:
                    dt = self.timestamps[-1] - self.timestamps[0]
                    if dt > 0:
                        self.hz = (len(self.timestamps) - 1) / dt
                self.vx = msg.twist.twist.linear.x
                self.vtheta = msg.twist.twist.angular.z

        from rclpy.executors import SingleThreadedExecutor
        sub = node.create_subscription(Odometry, "/odom", cb, qos)
        executor = SingleThreadedExecutor()
        executor.add_node(node)

        while not self.stop_event.is_set():
            executor.spin_once(timeout_sec=0.2)
            with self.lock:
                if self.last_msg_time > 0 and (time.time() - self.last_msg_time > 2.0):
                    self.has_odom = False

        executor.remove_node(node)
        node.destroy_node()

    def get_status(self):
        with self.lock:
            active = (time.time() - self.last_msg_time < 2.0) if self.last_msg_time > 0 else False
            return {
                "active": active,
                "hz": self.hz if active else 0.0,
                "count": self.odom_count,
                "vx": self.vx if active else 0.0,
                "vtheta": self.vtheta if active else 0.0
            }

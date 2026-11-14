#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# autonomous_avoidance.py - Thuật toán Tự né vật cản thông minh (Potential Field / Sector VFH)
# ==============================================================================

import time
import math
import serial
import threading
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import LaserScan

# Cấu hình an toàn
MAX_FORWARD_SPEED = 0.12   # Vận tốc tiến tối đa rất chậm và an toàn: 0.12 m/s (~12 cm/s)
MIN_FORWARD_SPEED = 0.05   # Vận tốc bò chậm khi tiếp cận vật cản: 0.05 m/s
TURN_SPEED        = 0.60   # Vận tốc xoay góc chậm: 0.60 rad/s
CRITICAL_DIST_M   = 0.35   # Dưới 35cm: Dừng khẩn cấp và lùi xe
SLOWDOWN_DIST_M   = 0.70   # Dưới 70cm: Bắt đầu hãm tốc và tính góc rẽ né

class AutonomousAvoidanceNode(Node):
    def __init__(self):
        super().__init__('autonomous_avoidance')
        self.is_active = False
        self.ser = None
        self.lock = threading.Lock()
        
        # Mở cổng kết nối ESP32
        try:
            self.ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.1)
            self.get_logger().info('Đã mở cổng /dev/ttyUSB0 kết nối ESP32!')
        except Exception as e:
            self.get_logger().error(f'Không thể mở /dev/ttyUSB0: {e}')

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        self.sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, qos)
        self.get_logger().info('Thuật toán Né vật cản sẵn sàng. Đang chờ kích hoạt...')

    def send_cmd(self, cmd_str):
        if self.ser:
            with self.lock:
                try:
                    self.ser.write((cmd_str.strip() + '
').encode('utf-8'))
                except Exception as e:
                    self.get_logger().error(f'Lỗi gửi lệnh: {e}')

    def scan_callback(self, msg):
        if not self.is_active:
            return

        angle = msg.angle_min
        step = msg.angle_increment

        # Phân tích 3 sector chính phía trước xe:
        # Front: -25° đến +25°
        # Left:  +25° đến +75°
        # Right: -75° đến -25°
        front_dists = []
        left_dists = []
        right_dists = []

        for r in msg.ranges:
            if math.isfinite(r) and msg.range_min <= r <= msg.range_max:
                deg = math.degrees(angle)
                # Chuẩn hóa về [-180, 180]
                while deg > 180: deg -= 360
                while deg < -180: deg += 360

                if -25 <= deg <= 25:
                    front_dists.append(r)
                elif 25 < deg <= 75:
                    left_dists.append(r)
                elif -75 <= deg < -25:
                    right_dists.append(r)

            angle += step

        min_front = min(front_dists) if front_dists else 9.99
        min_left  = min(left_dists)  if left_dists  else 9.99
        min_right = min(right_dists) if right_dists else 9.99

        # LOGIC ĐIỀU KHIỂN NÉ THÔNG MINH
        # 1. Quá gần vật cản trước mặt (< 35cm): DỪNG & LÙI
        if min_front < CRITICAL_DIST_M:
            self.get_logger().warn(f'VẬT CẢN QUÁ GẦN ({min_front:.2f}m) -> Dừng và lùi!')
            self.send_cmd('V -0.06 0.0') # Lùi chậm 6cm/s
            time.sleep(0.3)
            # Rẽ về phía thoáng hơn
            if min_left > min_right:
                self.send_cmd(f'V 0.0 {TURN_SPEED}') # Xoay trái
            else:
                self.send_cmd(f'V 0.0 -{TURN_SPEED}') # Xoay phải
        
        # 2. Vật cản trong vùng cảnh báo (35cm - 70cm): Giảm tốc và bẻ lái né
        elif min_front < SLOWDOWN_DIST_M:
            # Tốc độ tỉ lệ thuận với khoảng cách (càng gần càng chậm)
            ratio = (min_front - CRITICAL_DIST_M) / (SLOWDOWN_DIST_M - CRITICAL_DIST_M)
            v = MIN_FORWARD_SPEED + ratio * (MAX_FORWARD_SPEED - MIN_FORWARD_SPEED)
            
            # Chọn hướng thoáng hơn để lượn qua
            if min_left > min_right:
                w = TURN_SPEED * (1.0 - ratio) # Bẻ lái sang trái
            else:
                w = -TURN_SPEED * (1.0 - ratio) # Bẻ lái sang phải

            self.send_cmd(f'V {v:.2f} {w:.2f}')

        # 3. Phía trước thoáng (> 70cm): Tiến thẳng với tốc độ an toàn
        else:
            # Tránh cọ sát hai bên hông
            w = 0.0
            if min_left < 0.35:
                w = -0.3 # Hơi dạt sang phải
            elif min_right < 0.35:
                w = 0.3  # Hơi dạt sang trái
            
            self.send_cmd(f'V {MAX_FORWARD_SPEED:.2f} {w:.2f}')

    def start(self):
        self.is_active = True
        self.get_logger().info('>>> ĐÃ KÍCH HOẠT CHẾ ĐỘ TỰ NÉ VẬT CẢN (TỐC ĐỘ CHẬM AN TOÀN) <<<')

    def stop(self):
        self.is_active = False
        self.send_cmd('STOP')
        self.get_logger().info('>>> ĐÃ DỪNG KHẨN CẤP / TẮT CHẾ ĐỘ TỰ NÉ <<<')

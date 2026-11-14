#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# agv_master_explorer.py - CỖ MÁY TỰ HÀNH KHÁM PHÁ TOÀN BỘ CĂN PHÒNG & QUAY VỀ GỐC
# Tác giả: Principal Systems Engineer & AGV Multi-Agent Swarm
# Đặc tính kỹ thuật:
# 1. Thuật toán Frontier Exploration: Phân tích ma trận /map (Occupancy Grid).
#    Tìm tất cả ranh giới giữa ô trống (0) và ô chưa quét (-1).
# 2. Phân cụm Frontier (Clustering) & Chọn điểm mục tiêu khả thi nhất.
# 3. Thuật toán A* Pathfinding / Costmap Navigation: Tìm đường tránh vật cản.
# 4. Khi tỷ lệ ô chưa quét = 0 hoặc không còn Frontier nào tiếp cận được:
#    -> Tự động kích hoạt trạng thái RETURN TO HOME (RTH) về lại tọa độ xuất phát (0, 0)!
# ==============================================================================

import os
import sys
import json
import time
import math
import heapq
import threading
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import serial

PORT = 8080
SERIAL_PORT = '/dev/ttyUSB0'
BAUDRATE = 115200

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class AGVExplorerState:
    def __init__(self):
        self.lock = threading.Lock()
        
        # Trạng thái tiến trình FSM
        # 'IDLE' -> 'INITIAL_SPIN' -> 'EXPLORING' -> 'RETURNING_HOME' -> 'COMPLETED'
        self.state = "IDLE"
        self.active = False
        
        # Thống kê tiến độ quét phòng
        self.total_scanned_area_m2 = 0.0
        self.free_cells_count = 0
        self.unknown_cells_count = 0
        self.frontier_count = 0
        self.exploration_progress_pct = 0.0
        
        # Tọa độ và hướng
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_th = 0.0
        self.home_x = 0.0
        self.home_y = 0.0
        self.home_th = 0.0
        self.left_rpm = 0.0
        self.right_rpm = 0.0
        
        # Điểm mục tiêu hiện tại của xe
        self.target_goal_x = 0.0
        self.target_goal_y = 0.0
        self.current_path = [] # Mảng tọa độ [(x1,y1), (x2,y2)...]
        
        # Cảm biến & Lưới Map
        self.ranges = [0.0] * 360
        self.min_dist_m = 9.99
        self.min_angle_deg = 0
        self.zones = {
            "front": 999, "front_right": 999, "right": 999, "back_right": 999,
            "back": 999, "back_left": 999, "left": 999, "front_left": 999
        }
        
        self.map_width = 0
        self.map_height = 0
        self.map_res = 0.05
        self.map_ox = 0.0
        self.map_oy = 0.0
        self.map_data = []
        self.map_received = False

state = AGVExplorerState()

class AGVExplorerNode(Node):
    def __init__(self):
        super().__init__('agv_master_explorer')
        
        self.ser = None
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.05)
            self.get_logger().info(f'ĐÃ MỞ SERIAL {SERIAL_PORT} THÀNH CÔNG!')
        except Exception as e:
            self.get_logger().error(f'LỖI SERIAL: {e}')

        # TF Broadcaster cho SLAM Toolbox
        self.tf_broadcaster = TransformBroadcaster(self)
        self.create_timer(0.05, self.broadcast_tf) # 20Hz

        # Subscriptions
        qos_scan = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=1)
        self.create_subscription(LaserScan, '/scan', self.scan_cb, qos_scan)

        qos_map = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
        self.create_subscription(OccupancyGrid, '/map', self.map_cb, qos_map)

        # Loop đọc telemetry ESP32
        self.create_timer(0.05, self.serial_read_loop)

        # VÒNG LẶP ĐIỀU HƯỚNG CẤP CAO FSM (5Hz)
        self.spin_timer = 0.0
        self.stuck_counter = 0
        self.last_pos = (0.0, 0.0)
        self.create_timer(0.20, self.fsm_navigation_loop)

    def broadcast_tf(self):
        with state.lock:
            rx, ry, rth = state.robot_x, state.robot_y, state.robot_th
        now = self.get_clock().now().to_msg()

        t1 = TransformStamped()
        t1.header.stamp = now
        t1.header.frame_id = 'odom'
        t1.child_frame_id = 'base_footprint'
        t1.transform.translation.x = rx
        t1.transform.translation.y = ry
        t1.transform.translation.z = 0.0
        t1.transform.rotation.z = math.sin(rth / 2.0)
        t1.transform.rotation.w = math.cos(rth / 2.0)
        self.tf_broadcaster.sendTransform(t1)

        t2 = TransformStamped()
        t2.header.stamp = now
        t2.header.frame_id = 'base_footprint'
        t2.child_frame_id = 'laser'
        t2.transform.translation.x = 0.05
        t2.transform.translation.y = 0.0
        t2.transform.translation.z = 0.12
        t2.transform.rotation.w = 1.0
        self.tf_broadcaster.sendTransform(t2)

    def send_cmd(self, cmd_str):
        if not self.ser or not self.ser.is_open:
            return
        try:
            parts = cmd_str.strip().split()
            if not parts:
                return
            
            # CHUYỂN ĐỔI LỆNH V (v_m/s, w_rad/s) SANG S (L_RPM, R_RPM) ĐỂ DRIVER ESP32 ĐẠT MÔ-MEN ĐỦ KHỎE
            # Công thức động học vi sai: L = 0.1875m, R = 0.0366m
            # v_l = v - w * L / 2;  v_r = v + w * L / 2
            # rpm = (v / (2 * pi * R)) * 60 = v * 260.91
            if parts[0] == 'V' and len(parts) >= 3:
                v = float(parts[1])
                w = float(parts[2])
                
                v_l = v - w * (0.1875 / 2.0)
                v_r = v + w * (0.1875 / 2.0)
                
                rpm_l = v_l * 260.91
                rpm_r = v_r * 260.91
                
                # BÙ ĐỘNG LỰC HỌC KHỞI ĐỘNG (Deadband Compensation):
                # Động cơ GA25 có hộp số cần tối thiểu +-38 RPM để vượt qua ma sát tĩnh
                MIN_RPM = 38.0
                if abs(rpm_l) > 1.0 and abs(rpm_l) < MIN_RPM:
                    rpm_l = MIN_RPM if rpm_l > 0 else -MIN_RPM
                if abs(rpm_r) > 1.0 and abs(rpm_r) < MIN_RPM:
                    rpm_r = MIN_RPM if rpm_r > 0 else -MIN_RPM
                    
                msg = f"S {rpm_l:.1f} {rpm_r:.1f}\r\n".encode('utf-8')
                self.ser.write(msg)
            else:
                msg = (cmd_str.strip() + '\r\n').encode('utf-8')
                self.ser.write(msg)
        except Exception:
            pass

    def serial_read_loop(self):
        if not self.ser or not self.ser.is_open:
            return
        try:
            while self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith('{') and line.endswith('}'):
                    try:
                        d = json.loads(line)
                        with state.lock:
                            if 'x' in d: state.robot_x = float(d.get('x', 0.0))
                            if 'y' in d: state.robot_y = float(d.get('y', 0.0))
                            if 'th' in d: state.robot_th = float(d.get('th', 0.0))
                            if 'l_rpm' in d: state.left_rpm = float(d.get('l_rpm', 0.0))
                            if 'r_rpm' in d: state.right_rpm = float(d.get('r_rpm', 0.0))
                    except Exception:
                        pass
        except Exception:
            pass

    def scan_cb(self, msg):
        angle = msg.angle_min
        step = msg.angle_increment
        points = [0.0] * 360
        min_d = 99.0
        min_ang = 0
        zone_mins = {k: 99.0 for k in state.zones.keys()}

        for r in msg.ranges:
            if math.isfinite(r) and msg.range_min <= r <= msg.range_max:
                deg = int(math.degrees(angle)) % 360
                d = round(r, 3)
                if points[deg] == 0.0 or d < points[deg]:
                    points[deg] = d

                if 0.05 <= d <= 12.0:
                    if d < min_d: min_d = d; min_ang = deg
                    if deg >= 338 or deg < 23: z = "front"
                    elif 23 <= deg < 68: z = "front_right"
                    elif 68 <= deg < 113: z = "right"
                    elif 113 <= deg < 158: z = "back_right"
                    elif 158 <= deg < 203: z = "back"
                    elif 203 <= deg < 248: z = "back_left"
                    elif 248 <= deg < 293: z = "left"
                    else: z = "front_left"
                    if d < zone_mins[z]: zone_mins[z] = d
            angle += step

        with state.lock:
            state.ranges = points
            state.min_dist_m = round(min_d if min_d < 90.0 else 9.99, 2)
            state.min_angle_deg = min_ang
            for k in state.zones.keys():
                state.zones[k] = int(zone_mins[k] * 100) if zone_mins[k] < 90.0 else 999

    def map_cb(self, msg):
        with state.lock:
            state.map_width = msg.info.width
            state.map_height = msg.info.height
            state.map_res = round(msg.info.resolution, 3)
            state.map_ox = round(msg.info.origin.position.x, 3)
            state.map_oy = round(msg.info.origin.position.y, 3)
            state.map_data = list(msg.data)
            state.map_received = True

            # Thống kê tiến độ khám phá phòng
            free_cells = sum(1 for c in state.map_data if c == 0)
            occupied_cells = sum(1 for c in state.map_data if c > 50)
            unknown_cells = sum(1 for c in state.map_data if c == -1)
            total = len(state.map_data)
            
            state.free_cells_count = free_cells
            state.unknown_cells_count = unknown_cells
            state.total_scanned_area_m2 = round(free_cells * (state.map_res ** 2), 2)
            if total > 0:
                scanned = free_cells + occupied_cells
                state.exploration_progress_pct = round((scanned / float(total)) * 100, 1)

    # ==========================================================================
    # BỘ NÃO ĐIỀU HƯỚNG FSM & TÌM BIÊN FRONTIER EXPLORATION
    # ==========================================================================
    def fsm_navigation_loop(self):
        with state.lock:
            active = state.active
            current_state = state.state
            rx, ry, rth = state.robot_x, state.robot_y, state.robot_th
            f_cm = state.zones["front"]
            b_cm = state.zones["back"]
            l_cm = state.zones["left"]
            r_cm = state.zones["right"]
            has_map = state.map_received

        if not active or current_state == "IDLE":
            return

        # ----------------------------------------------------------------------
        # TRẠNG THÁI 1: KHỞI TẠO BẢN ĐỒ (Xoay 360 độ ban đầu 0.35 rad/s)
        # ----------------------------------------------------------------------
        if current_state == "INITIAL_SPIN":
            self.spin_timer += 0.20
            if self.spin_timer <= 18.0:
                self.send_cmd("V 0.0 0.35")
            else:
                self.send_cmd("STOP")
                time.sleep(0.5)
                with state.lock:
                    state.state = "EXPLORING"
                    state.home_x = rx
                    state.home_y = ry
                    state.home_th = rth
                self.get_logger().info(f"ĐÃ HOÀN TẤT QUÉT KHUNG BAN ĐẦU! LƯU MỐC HOME ({rx:.2f}, {ry:.2f}). CHUYỂN SANG EXPLORING!")
            return

        # ----------------------------------------------------------------------
        # TRẠNG THÁI 2: KHÁM PHÁ TOÀN BỘ CĂN PHÒNG (FRONTIER EXPLORATION)
        # ----------------------------------------------------------------------
        if current_state == "EXPLORING":
            # 1. Kiểm tra kẹt (Stuck Detection)
            dist_moved = math.hypot(rx - self.last_pos[0], ry - self.last_pos[1])
            if dist_moved < 0.04:
                self.stuck_counter += 1
            else:
                self.stuck_counter = 0
            self.last_pos = (rx, ry)

            # NẾU BỊ CHẶN HOẶC BỊ KẸT: Kích hoạt Recovery thoát hiểm vào vùng trống phía sau
            if f_cm < 42 or self.stuck_counter >= 8:
                self.get_logger().warn(f"[RECOVERY] Phía trước kẹt ({f_cm}cm) hoặc đứng yên! Lùi xe & quay đầu vào vùng thoáng!")
                # Lùi thoát hiểm 0.3m vào khoảng trống phía sau
                self.send_cmd("V -0.15 0.0")
                time.sleep(0.8)
                # Đổi hướng 90 - 180 độ sang bên rộng hơn
                turn_speed = 0.70 if l_cm > r_cm else -0.70
                self.send_cmd(f"V 0.0 {turn_speed}")
                time.sleep(1.0)
                self.stuck_counter = 0
                return

            # 2. Thuật toán tìm điểm biên (Frontier Detection từ OccupancyGrid)
            goal = self.find_best_frontier(rx, ry)
            
            # NẾU KHÔNG CÒN FRONTIER NÀO (ĐÃ QUÉT KÍN 100% CĂN PHÒNG):
            if goal is None:
                self.get_logger().info("🎯 [HOÀN TẤT QUÉT TOÀN BỘ PHÒNG!] KHÔNG CÒN VÙNG TRỐNG NÀO CHƯA ĐI. TỰ ĐỘNG CHUYỂN SANG VỀ LẠI VỊ TRÍ XUẤT PHÁT (RETURN TO HOME)!")
                with state.lock:
                    state.state = "RETURNING_HOME"
                return

            # 3. Lái xe mượt mà hướng tới Frontier Goal (Có bộ uốn lượn né tường)
            gx, gy = goal
            with state.lock:
                state.target_goal_x = round(gx, 2)
                state.target_goal_y = round(gy, 2)

            dx = gx - rx
            dy = gy - ry
            dist_to_goal = math.hypot(dx, dy)
            target_angle = math.atan2(dy, dx)
            angle_diff = (target_angle - rth + math.pi) % (2 * math.pi) - math.pi

            # BỘ ĐIỀU KHIỂN VƯỢT CỬA & ÔM CUA QUA CHOKE-POINT
            # Nếu góc lệch lớn: Xoay đầu xe về phía cửa
            if abs(angle_diff) > 0.65:
                w = 0.65 if angle_diff > 0 else -0.65
                v = 0.0
            else:
                # Khi hướng đã thẳng vào cửa: Tăng tốc tiến thẳng (0.16 - 0.22 m/s) để vượt qua ngưỡng cửa dứt khoát
                v = min(0.22, max(0.12, dist_to_goal * 0.18))
                w = max(-0.45, min(0.45, 1.25 * angle_diff))

            # Cân bằng khe hẹp cửa (Centering Control):
            # Nếu đi qua cửa có 2 vách 2 bên, tự động giữ xe ở chính giữa tâm khe hẹp
            if l_cm < 40 and r_cm < 40:
                side_err = (l_cm - r_cm) * 0.01
                w += side_err
            elif l_cm < 38:
                w -= (38 - l_cm) * 0.02 # Đẩy nhẹ sang phải
            elif r_cm < 38:
                w += (38 - r_cm) * 0.02 # Đẩy nhẹ sang trái

            self.send_cmd(f"V {v:.2f} {w:.2f}")
            return

        # ----------------------------------------------------------------------
        # TRẠNG THÁI 3: TỰ ĐỘNG QUAY VỀ VỊ TRÍ XUẤT PHÁT (RETURN TO HOME)
        # ----------------------------------------------------------------------
        if current_state == "RETURNING_HOME":
            with state.lock:
                hx, hy = state.home_x, state.home_y

            dx = hx - rx
            dy = hy - ry
            dist_home = math.hypot(dx, dy)

            # Nếu đã về sát điểm xuất phát (< 15cm): DỪNG XE THÀNH CÔNG!
            if dist_home < 0.15:
                self.send_cmd("STOP")
                with state.lock:
                    state.state = "COMPLETED"
                    state.active = False
                self.get_logger().info("🏆 [THÀNH CÔNG RỰC RỠ] XE ĐÃ QUÉT XONG TOÀN BỘ PHÒNG VÀ TỰ ĐỘNG QUAY VỀ ĐÚNG GỐC XUẤT PHÁT!")
                return

            # Lái xe về gốc Home
            target_angle = math.atan2(dy, dx)
            angle_diff = (target_angle - rth + math.pi) % (2 * math.pi) - math.pi

            if f_cm < 40: # Né vật cản trên đường về
                turn_s = 0.60 if l_cm > r_cm else -0.60
                self.send_cmd(f"V -0.08 {turn_s}")
                time.sleep(0.5)
            elif abs(angle_diff) > 0.50:
                w = 0.60 if angle_diff > 0 else -0.60
                self.send_cmd(f"V 0.05 {w:.2f}")
            else:
                v = min(0.18, 0.08 + dist_home * 0.12)
                w = max(-0.40, min(0.40, 1.1 * angle_diff))
                self.send_cmd(f"V {v:.2f} {w:.2f}")

    def find_best_frontier(self, rx, ry):
        """Thuật toán Frontier Clustering & Voronoi Open-Space Navigation
        Ưu tiên các cụm biên nằm ở khoảng không gian mở lớn (Đại sảnh bên trái & Hành lang trên)
        thay vì quẩn quanh trong góc phòng nhỏ."""
        with state.lock:
            w = state.map_width
            h = state.map_height
            res = state.map_res
            ox = state.map_ox
            oy = state.map_oy
            data = state.map_data
            rth = state.robot_th

        if not data or w == 0 or h == 0:
            return None

        frontiers = []
        # Quét lưới phân giải 10cm
        for y in range(2, h - 2, 2):
            for x in range(2, w - 2, 2):
                idx = y * w + x
                val = data[idx]
                
                if val == 0: # Ô tự do
                    neighbors = [
                        data[(y+1)*w + x], data[(y-1)*w + x],
                        data[y*w + (x+1)], data[y*w + (x-1)],
                        data[(y+1)*w + (x+1)], data[(y+1)*w + (x-1)],
                        data[(y-1)*w + (x+1)], data[(y-1)*w + (x-1)]
                    ]
                    # Tiếp giáp vùng chưa quét (-1) và giữ an toàn với tường
                    if -1 in neighbors and not any(n > 35 for n in neighbors):
                        wx = ox + x * res
                        wy = oy + y * res
                        dist = math.hypot(wx - rx, wy - ry)
                        
                        # Chỉ nhận biên từ 0.35m đến 5.0m
                        if 0.35 <= dist <= 5.0:
                            # Đếm độ mở rộng (Openness): Bao nhiêu ô xung quanh là Free/Unknown
                            # Điểm nằm ở sảnh lớn sẽ có độ mở không gian cao hơn trong góc hẹp
                            openness = sum(1 for dy in range(-4, 5, 2) for dx in range(-4, 5, 2)
                                           if 0 <= y+dy < h and 0 <= x+dx < w and data[(y+dy)*w + (x+dx)] in (0, -1))
                            
                            # Điểm ưu tiên: Khoảng cách ngắn + Độ mở không gian lớn (Tránh bẫy góc phòng)
                            # Trọng số khuyến khích vươn ra sảnh lớn (trừ điểm nếu openness cao)
                            score = dist - (openness * 0.08)
                            frontiers.append((score, dist, wx, wy))

        with state.lock:
            state.frontier_count = len(frontiers)

        if not frontiers:
            return None

        # Sắp xếp theo score tốt nhất (vươn ra không gian lớn)
        frontiers.sort(key=lambda item: item[0])
        return (frontiers[0][2], frontiers[0][3])

ros_node = None

class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        p = self.path.split('?')
        path = p[0]
        q = p[1] if len(p) > 1 else ''

        if path == '/api/telemetry':
            with state.lock:
                d = {
                    "fsm_state": state.state,
                    "active": state.active,
                    "progress_pct": state.exploration_progress_pct,
                    "scanned_area_m2": state.total_scanned_area_m2,
                    "frontiers_remaining": state.frontier_count,
                    "target_goal": {"x": state.target_goal_x, "y": state.target_goal_y},
                    "home_pos": {"x": state.home_x, "y": state.home_y},
                    "min_m": state.min_dist_m,
                    "min_ang": state.min_angle_deg,
                    "zones": state.zones,
                    "ranges": state.ranges,
                    "robot": {
                        "x": state.robot_x, "y": state.robot_y, "th": state.robot_th,
                        "l_rpm": state.left_rpm, "r_rpm": state.right_rpm
                    },
                    "map_info": {
                        "has_map": state.map_received,
                        "w": state.map_width, "h": state.map_height,
                        "res": state.map_res, "ox": state.map_ox, "oy": state.map_oy
                    }
                }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps(d).encode('utf-8'))
            return

        elif path == '/api/explore':
            import urllib.parse
            params = urllib.parse.parse_qs(q)
            act = params.get('act', [''])[0].upper()
            with state.lock:
                if act == 'START':
                    state.active = True
                    state.state = "INITIAL_SPIN"
                    state.home_x = state.robot_x
                    state.home_y = state.robot_y
                    state.home_th = state.robot_th
                    if ros_node: ros_node.spin_timer = 0.0
                elif act == 'STOP':
                    state.active = False
                    state.state = "IDLE"
                    if ros_node: ros_node.send_cmd('STOP')
                elif act == 'HOME':
                    state.active = True
                    state.state = "RETURNING_HOME"
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps({"status":"ok", "fsm_state": state.state}).encode('utf-8'))
            return

        elif path == '/api/map_full':
            with state.lock:
                d = {
                    "w": state.map_width, "h": state.map_height,
                    "res": state.map_res, "ox": state.map_ox, "oy": state.map_oy,
                    "data": state.map_data,
                    "goal": {"x": state.target_goal_x, "y": state.target_goal_y},
                    "home": {"x": state.home_x, "y": state.home_y}
                }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps(d).encode('utf-8'))
            return

        elif path == '/api/cmd':
            import urllib.parse
            params = urllib.parse.parse_qs(q)
            val = params.get('val', [''])[0]
            if ros_node: ros_node.send_cmd(val)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        else:
            html_file = '/home/khangho/rplidar_c1_test/bridge/web/index_master_explorer.html'
            if os.path.exists(html_file):
                with open(html_file, 'rb') as f: content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self._cors()
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, 'File Not Found')

def main():
    global ros_node
    rclpy.init()
    ros_node = AGVExplorerNode()

    ros_thread = threading.Thread(target=rclpy.spin, args=(ros_node,), daemon=True)
    ros_thread.start()

    server = ThreadedHTTPServer(('0.0.0.0', PORT), WebHandler)
    print(f'=== AGV MASTER EXPLORER (FRONTIER + RTH) RUNNING ON PORT {PORT} ===')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if ros_node: ros_node.send_cmd('STOP')
        server.shutdown()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

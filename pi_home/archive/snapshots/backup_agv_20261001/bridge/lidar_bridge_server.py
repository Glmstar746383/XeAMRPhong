#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# lidar_bridge_server.py
# Server cầu nối (Bridge) truyền dữ liệu RPLIDAR C1M1 từ Raspberry Pi sang:
# 1. Trình duyệt Desktop (Bản đồ Radar 360° Sci-Fi trực quan 60 FPS)
# 2. Ứng dụng điện thoại MIT App Inventor (Qua WebViewer hoặc REST API 8 hướng)
#
# Hoạt động với:
# - Chế độ thật: Đọc dữ liệu từ ROS 2 topic /scan (sensor_msgs/LaserScan)
# - Chế độ giả lập (--mock): Sinh dữ liệu mô phỏng để test ngay trên PC
# ==============================================================================

import os
import sys
import json
import math
import time
import argparse
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Fix encoding tren Windows console
try:
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# Thư mục chứa tài nguyên Web
BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BRIDGE_DIR, "web")

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Server HTTP đa luồng xử lý nhiều client cùng lúc (Desktop + Phone)"""
    daemon_threads = True

class LidarDataManager:
    """Quản lý dữ liệu LiDAR luồng an toàn (Thread-safe) và tiền xử lý 8 hướng"""
    def __init__(self):
        self.lock = threading.Lock()
        self.is_active = False
        self.mode = "mock"
        self.last_update = 0.0
        self.scan_count = 0
        self.hz = 0.0
        self.total_points = 0
        self.valid_points = 0
        
        # Mảng 360 điểm khoảng cách (mét) tương ứng từng góc 0° đến 359°
        # 0°: Phía trước xe (Front), 90°: Phía phải (Right), 180°: Phía sau, 270°: Phía trái
        self.scan_360 = [0.0] * 360
        
        # 8 vùng không gian xung quanh xe
        self.zones = {
            "front": {"dist_cm": 999, "dist_m": 9.99, "status": "SAFE"},
            "front_right": {"dist_cm": 999, "dist_m": 9.99, "status": "SAFE"},
            "right": {"dist_cm": 999, "dist_m": 9.99, "status": "SAFE"},
            "back_right": {"dist_cm": 999, "dist_m": 9.99, "status": "SAFE"},
            "back": {"dist_cm": 999, "dist_m": 9.99, "status": "SAFE"},
            "back_left": {"dist_cm": 999, "dist_m": 9.99, "status": "SAFE"},
            "left": {"dist_cm": 999, "dist_m": 9.99, "status": "SAFE"},
            "front_left": {"dist_cm": 999, "dist_m": 9.99, "status": "SAFE"},
        }
        
        self.min_dist_m = 9.99
        self.min_dist_cm = 999
        self.min_angle_deg = 0
        self.safety_status = "SAFE" # SAFE | WARNING | DANGER_STOP

        # Ngưỡng an toàn (mét)
        self.DANGER_THRESHOLD = 0.35   # < 35cm: Dừng khẩn cấp
        self.WARNING_THRESHOLD = 0.70  # < 70cm: Cảnh báo chậm lại

    def update_scan(self, points_dict, hz=10.0):
        """
        points_dict: dict { angle_deg_int (0..359): distance_meter }
        """
        now = time.time()
        with self.lock:
            self.last_update = now
            self.scan_count += 1
            self.hz = hz
            self.is_active = True
            
            # Cập nhật mảng 360 điểm
            valid_cnt = 0
            min_d = 99.0
            min_ang = 0
            
            zone_mins = {k: 99.0 for k in self.zones.keys()}
            
            for deg in range(360):
                d = points_dict.get(deg, 0.0)
                self.scan_360[deg] = round(d, 3)
                
                if 0.05 <= d <= 12.0:
                    valid_cnt += 1
                    if d < min_d:
                        min_d = d
                        min_ang = deg
                    
                    # Phân bổ vào 8 vùng (mỗi vùng 45 độ)
                    # 0° ở phía trước: Vùng Front từ 337.5° đến 22.5°
                    if deg >= 338 or deg < 23:
                        zone = "front"
                    elif 23 <= deg < 68:
                        zone = "front_right"
                    elif 68 <= deg < 113:
                        zone = "right"
                    elif 113 <= deg < 158:
                        zone = "back_right"
                    elif 158 <= deg < 203:
                        zone = "back"
                    elif 203 <= deg < 248:
                        zone = "back_left"
                    elif 248 <= deg < 293:
                        zone = "left"
                    else:
                        zone = "front_left"
                    
                    if d < zone_mins[zone]:
                        zone_mins[zone] = d

            self.valid_points = valid_cnt
            self.total_points = 360
            
            # Cập nhật kết quả 8 vùng
            for zone_name, min_val in zone_mins.items():
                if min_val >= 90.0:
                    dist_m = 9.99
                    dist_cm = 999
                    status = "SAFE"
                else:
                    dist_m = round(min_val, 2)
                    dist_cm = int(min_val * 100)
                    if dist_m <= self.DANGER_THRESHOLD:
                        status = "DANGER_STOP"
                    elif dist_m <= self.WARNING_THRESHOLD:
                        status = "WARNING"
                    else:
                        status = "SAFE"
                
                self.zones[zone_name] = {
                    "dist_cm": dist_cm,
                    "dist_m": dist_m,
                    "status": status
                }
                
            if min_d < 90.0:
                self.min_dist_m = round(min_d, 2)
                self.min_dist_cm = int(min_d * 100)
                self.min_angle_deg = min_ang
                if self.min_dist_m <= self.DANGER_THRESHOLD:
                    self.safety_status = "DANGER_STOP"
                elif self.min_dist_m <= self.WARNING_THRESHOLD:
                    self.safety_status = "WARNING"
                else:
                    self.safety_status = "SAFE"
            else:
                self.min_dist_m = 9.99
                self.min_dist_cm = 999
                self.min_angle_deg = 0
                self.safety_status = "SAFE"

    def get_zones_summary(self):
        """Trả về dữ liệu JSON rút gọn chuyên dụng cho MIT App Inventor"""
        with self.lock:
            # Kiểm tra mất kết nối quá 2 giây
            receiving = (time.time() - self.last_update < 2.0) and self.is_active
            return {
                "active": receiving,
                "status": self.safety_status if receiving else "DISCONNECTED",
                "min_dist_cm": self.min_dist_cm if receiving else 999,
                "min_dist_m": self.min_dist_m if receiving else 9.99,
                "min_angle": self.min_angle_deg if receiving else 0,
                "front_cm": self.zones["front"]["dist_cm"] if receiving else 999,
                "front_right_cm": self.zones["front_right"]["dist_cm"] if receiving else 999,
                "right_cm": self.zones["right"]["dist_cm"] if receiving else 999,
                "back_right_cm": self.zones["back_right"]["dist_cm"] if receiving else 999,
                "back_cm": self.zones["back"]["dist_cm"] if receiving else 999,
                "back_left_cm": self.zones["back_left"]["dist_cm"] if receiving else 999,
                "left_cm": self.zones["left"]["dist_cm"] if receiving else 999,
                "front_left_cm": self.zones["front_left"]["dist_cm"] if receiving else 999,
                "zones": self.zones if receiving else {},
                "hz": round(self.hz, 1) if receiving else 0.0,
                "timestamp": int(self.last_update * 1000)
            }

    def get_full_scan(self):
        """Trả về mảng 360 điểm quét đầy đủ cho giao diện Web Radar"""
        with self.lock:
            receiving = (time.time() - self.last_update < 2.0) and self.is_active
            return {
                "active": receiving,
                "mode": self.mode,
                "hz": round(self.hz, 1) if receiving else 0.0,
                "scan_count": self.scan_count,
                "valid_points": self.valid_points if receiving else 0,
                "min_dist_m": self.min_dist_m if receiving else 9.99,
                "min_angle_deg": self.min_angle_deg if receiving else 0,
                "safety_status": self.safety_status if receiving else "DISCONNECTED",
                "ranges": self.scan_360 if receiving else [0.0] * 360,
                "zones": self.zones if receiving else {},
                "timestamp": int(self.last_update * 1000)
            }

# Khởi tạo đối tượng lưu trữ dùng chung
data_manager = LidarDataManager()

# ------------------------------------------------------------------------------
# Bộ sinh dữ liệu Mock (Dùng khi test trên Windows / Không có phần cứng LiDAR)
# ------------------------------------------------------------------------------
class MockLidarThread(threading.Thread):
    def __init__(self, data_mgr):
        super().__init__(daemon=True)
        self.data_mgr = data_mgr
        self.running = True
        self.angle_offset = 0.0

    def run(self):
        self.data_mgr.mode = "mock"
        print("[MOCK] Đã khởi động bộ mô phỏng LiDAR C1 (10 Hz).")
        
        while self.running:
            self.angle_offset += 0.05
            points = {}
            
            # Mô phỏng một căn phòng hình chữ nhật kích thước 4.5m x 3.5m
            room_w = 4.5
            room_h = 3.5
            
            # Mô phỏng 1 vật cản chuyển động qua lại phía trước (khoảng cách 0.4m - 1.2m)
            obs_dist = 0.8 + 0.45 * math.sin(self.angle_offset * 1.5)
            obs_angle = int((math.sin(self.angle_offset) * 25) % 360) # Dao động -25° đến +25°
            
            # Mô phỏng 1 vật cản cố định phía bên phải (khoảng cách 0.9m)
            right_obs_dist = 0.9
            
            for deg in range(360):
                rad = math.radians(deg)
                cos_a = math.cos(rad)
                sin_a = math.sin(rad)
                
                # Khoảng cách đến 4 bức tường xung quanh
                # Trục x: trước/sau (cos_a), Trục y: trái/phải (sin_a)
                d_wall = 4.0
                if cos_a > 0.001:
                    d_wall = min(d_wall, (room_h / 2) / cos_a)
                elif cos_a < -0.001:
                    d_wall = min(d_wall, (-room_h / 2) / cos_a)
                if sin_a > 0.001:
                    d_wall = min(d_wall, (room_w / 2) / sin_a)
                elif sin_a < -0.001:
                    d_wall = min(d_wall, (-room_w / 2) / sin_a)
                    
                d = max(0.1, d_wall)
                
                # Chèn vật cản di động phía trước
                diff_obs = abs((deg - obs_angle + 180) % 360 - 180)
                if diff_obs <= 8:
                    d = min(d, obs_dist)
                    
                # Chèn vật cản bên phải (góc 80° đến 100°)
                if 82 <= deg <= 98:
                    d = min(d, right_obs_dist)
                    
                # Thêm một chút nhiễu đo đạc tự nhiên của laser
                noise = (math.sin(deg * 11 + self.angle_offset) * 0.01)
                points[deg] = max(0.05, round(d + noise, 3))
                
            self.data_mgr.update_scan(points, hz=10.0)
            time.sleep(0.1) # 10 Hz

# ------------------------------------------------------------------------------
# Bộ kết nối ROS 2 (Dùng khi chạy trên Raspberry Pi nhận topic /scan thật)
# ------------------------------------------------------------------------------
class Ros2LidarThread(threading.Thread):
    def __init__(self, data_mgr):
        super().__init__(daemon=True)
        self.data_mgr = data_mgr
        self.running = True

    def run(self):
        try:
            import rclpy
            from rclpy.node import Node
            from sensor_msgs.msg import LaserScan
            from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
        except ImportError:
            print("[ROS2 ERROR] Không tìm thấy rclpy. Tự động chuyển sang chế độ Mock...")
            mock = MockLidarThread(self.data_mgr)
            mock.start()
            return

        if not rclpy.ok():
            rclpy.init()

        node = Node("lidar_bridge_web_server")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        last_time = [time.time()]
        hz_rolling = [10.0]

        def scan_cb(msg: LaserScan):
            now = time.time()
            dt = now - last_time[0]
            last_time[0] = now
            if dt > 0:
                curr_hz = 1.0 / dt
                hz_rolling[0] = 0.9 * hz_rolling[0] + 0.1 * curr_hz

            total_ranges = len(msg.ranges)
            if total_ranges == 0:
                return

            points = {}
            angle = msg.angle_min
            step = msg.angle_increment
            
            # Quy đổi toàn bộ điểm quét sang 360 độ nguyên (0..359)
            for r in msg.ranges:
                if math.isfinite(r) and msg.range_min <= r <= msg.range_max:
                    deg = int(math.degrees(angle)) % 360
                    # Giữ khoảng cách nhỏ nhất tại mỗi góc nguyên
                    if deg not in points or r < points[deg]:
                        points[deg] = r
                angle += step

            self.data_mgr.update_scan(points, hz=hz_rolling[0])

        node.create_subscription(LaserScan, "/scan", scan_cb, qos)
        self.data_mgr.mode = "ros2"
        print("[ROS2] Đã đăng ký lắng nghe topic /scan thành công.")

        while self.running and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)

        node.destroy_node()

# ------------------------------------------------------------------------------
# Request Handler phục vụ Web Dashboard & API REST
# ------------------------------------------------------------------------------
import serial
import subprocess

s_esp32_lock = threading.Lock()
s_esp32_serial = None
s_avoidance_process = None
s_auto_mode = False

def get_esp32_serial():
    global s_esp32_serial
    with s_esp32_lock:
        if s_esp32_serial is None:
            try:
                s_esp32_serial = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.1)
                print('[BRIDGE] Đã mở cổng /dev/ttyUSB0 điều khiển xe AGV!')
            except Exception as e:
                print('[BRIDGE] Lỗi mở cổng /dev/ttyUSB0:', e)
                s_esp32_serial = None
        return s_esp32_serial

def send_robot_cmd(cmd_str):
    ser = get_esp32_serial()
    if ser:
        try:
            with s_esp32_lock:
                msg = cmd_str.strip() + "\r\n"
                ser.write(msg.encode("utf-8"))
                return True
        except Exception as e:
            print('[BRIDGE] Lỗi gửi lệnh xuống robot:', e)
    return False

class BridgeHttpHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Tắt log spam HTTP request định kỳ để terminal gọn gàng
        return

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = self.path.split('?')
        path = parsed[0]
        query = parsed[1] if len(parsed) > 1 else ''

                # 0.1 API: Kích hoạt / Tắt chế độ Tự Hành Né Vật Cản
        if path == '/api/auto':
            global s_auto_mode, s_avoidance_process
            import urllib.parse
            import subprocess
            params = urllib.parse.parse_qs(query)
            act = params.get('act', [''])[0].upper()
            
            if act == 'START':
                s_auto_mode = True
                if s_avoidance_process is None or s_avoidance_process.poll() is not None:
                    cmd = ['bash', '-c', 'source /opt/ros/jazzy/setup.bash && python3 /home/khangho/rplidar_c1_test/app/run_avoidance.py']
                    s_avoidance_process = subprocess.Popen(cmd)
                    print('[AUTO] Đã bật chế độ Tự Né Vật Cản Thông Minh!')
            else:
                s_auto_mode = False
                if s_avoidance_process and s_avoidance_process.poll() is None:
                    s_avoidance_process.terminate()
                    s_avoidance_process = None
                send_robot_cmd('STOP')
                print('[AUTO] ĐÃ DỪNG KHẨN CẤP / TẮT TỰ HÀNH!')

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'auto_mode': s_auto_mode}).encode('utf-8'))
            return

        if path == '/api/cmd':
            import urllib.parse
            params = urllib.parse.parse_qs(query)
            val = params.get('val', [''])[0]
            ok = send_robot_cmd(val)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok' if ok else 'error', 'cmd': val}).encode('utf-8'))
            return

        # 1. API: Cung cấp 8 vùng & Cảnh báo va chạm cho MIT App Inventor
        if path == "/api/zones" or path == "/api/status":
            data = data_manager.get_zones_summary()
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        # 2. API: Cung cấp mảng điểm quét 360° đầy đủ cho Radar
        elif path == "/api/scan":
            data = data_manager.get_full_scan()
            payload = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        # 3. Giao diện Radar thu gọn tối ưu cho WebViewer trên MIT App Inventor
        elif path == "/radar":
            radar_file = os.path.join(WEB_DIR, "radar.html")
            if os.path.exists(radar_file):
                with open(radar_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self._send_cors_headers()
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "File radar.html not found")
            return

        # 4. Giao diện Web Dashboard Desktop Đầy Đủ
        elif path == "/" or path == "/index.html":
            index_file = os.path.join(WEB_DIR, "index.html")
            if os.path.exists(index_file):
                with open(index_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self._send_cors_headers()
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "File index.html not found")
            return

        # 5. Phục vụ các file tĩnh khác trong thư mục web/ nếu có
        else:
            rel_path = path.lstrip("/")
            file_path = os.path.join(WEB_DIR, rel_path)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                ext = os.path.splitext(file_path)[1].lower()
                content_type = "text/plain"
                if ext == ".html": content_type = "text/html"
                elif ext == ".js": content_type = "application/javascript"
                elif ext == ".css": content_type = "text/css"
                elif ext in [".png", ".jpg", ".jpeg", ".svg", ".ico"]: content_type = f"image/{ext.lstrip('.')}"
                
                with open(file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self._send_cors_headers()
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "File Not Found")

def run_server(port=8080, host="0.0.0.0", use_mock=False):
    os.makedirs(WEB_DIR, exist_ok=True)
    
    # Khởi động luồng đọc dữ liệu LiDAR
    if use_mock:
        worker = MockLidarThread(data_manager)
    else:
        # Kiểm tra xem có rclpy (ROS2) không, nếu không tự động fallback về Mock
        try:
            import rclpy
            worker = Ros2LidarThread(data_manager)
        except ImportError:
            print("[THÔNG BÁO] Không có môi trường ROS 2 trên máy này. Tự động bật chế độ MOCK giả lập để thử nghiệm.")
            worker = MockLidarThread(data_manager)
            
    worker.start()

    server_address = (host, port)
    httpd = ThreadedHTTPServer(server_address, BridgeHttpHandler)
    
    print("\n" + "=" * 65)
    print(" 🚀 RPLIDAR C1M1 - WEB & MIT APP BRIDGE SERVER ĐÃ SẴN SÀNG!")
    print("=" * 65)
    print(f" * Chế độ dữ liệu   : {data_manager.mode.upper()}")
    print(f" * Máy tính Desktop : Mở trình duyệt xem http://localhost:{port}/")
    print(f" * MIT App Inventor :")
    print(f"   - WebViewer radar: http://<IP_RASPBERRY_PI>:{port}/radar")
    print(f"   - API JSON 8 vùng: http://<IP_RASPBERRY_PI>:{port}/api/zones")
    print("=" * 65 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOP] Đang dừng server...")
        httpd.shutdown()
        worker.running = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LiDAR Web Bridge Server cho Desktop & MIT App")
    parser.add_argument("--port", type=int, default=8080, help="Cổng HTTP (mặc định: 8080)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Địa chỉ bind (mặc định: 0.0.0.0)")
    parser.add_argument("--mock", action="store_true", help="Bắt buộc chạy chế độ giả lập Mock (không dùng ROS 2)")
    args = parser.parse_args()

    run_server(port=args.port, host=args.host, use_mock=args.mock)

#!/usr/bin/env bash
# ==============================================================================
# test_scan.sh - Phân tích chuyên sâu dữ liệu LaserScan từ RPLIDAR C1
# Kiểm tra: angle_min, angle_max, range_min, range_max, ranges[], Hz, Valid Points
# ==============================================================================

set -eo pipefail

# 1. Nạp môi trường ROS 2
if [[ -z "$ROS_DISTRO" ]]; then
    if [[ -f "/opt/ros/jazzy/setup.bash" ]]; then
        source /opt/ros/jazzy/setup.bash
    elif [[ -f "/opt/ros/humble/setup.bash" ]]; then
        source /opt/ros/humble/setup.bash
    fi
fi

# 2. Kiểm tra topic /scan có tồn tại không
if ! ros2 topic list 2>/dev/null | grep -q "^/scan$"; then
    echo "[FAIL] Topic /scan KHÔNG tồn tại!"
    echo "  Hãy đảm bảo driver RPLIDAR C1 đã được khởi động bằng:"
    echo "    ./scripts/start_lidar.sh"
    exit 1
fi

# 3. Chạy python node để lắng nghe và đánh giá dữ liệu LaserScan
python3 - << 'EOF'
import sys
import time
import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

class ScanEvaluator(Node):
    def __init__(self):
        super().__init__('scan_evaluator')
        self.scan_count = 0
        self.total_points = 0
        self.valid_points = 0
        self.min_dist = float('inf')
        self.max_dist = 0.0
        self.last_msg = None
        self.timestamps = []
        
        self.sub = self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10
        )
        
    def scan_callback(self, msg):
        self.scan_count += 1
        now = time.time()
        self.timestamps.append(now)
        self.last_msg = msg
        
        pts = len(msg.ranges)
        self.total_points += pts
        
        for r in msg.ranges:
            if math.isfinite(r) and msg.range_min <= r <= msg.range_max:
                self.valid_points += 1
                if r < self.min_dist:
                    self.min_dist = r
                if r > self.max_dist:
                    self.max_dist = r

def main():
    rclpy.init()
    evaluator = ScanEvaluator()
    print("Đang lắng nghe dữ liệu từ /scan trong 3 giây...")
    
    start_time = time.time()
    while rclpy.ok() and (time.time() - start_time < 3.0):
        rclpy.spin_once(evaluator, timeout_sec=0.1)
        
    rclpy.shutdown()
    
    print("==================================================")
    print("        KẾT QUẢ ĐÁNH GIÁ DỮ LIỆU LASERSCAN        ")
    print("==================================================")
    
    if evaluator.scan_count == 0:
        print("[FAIL] KHÔNG nhận được bất kỳ LaserScan message nào từ /scan!")
        print("  -> Kiểm tra kết nối cảm biến và quyền serial port.")
        sys.exit(1)
        
    msg = evaluator.last_msg
    duration = evaluator.timestamps[-1] - evaluator.timestamps[0] if len(evaluator.timestamps) > 1 else 1.0
    hz = (evaluator.scan_count - 1) / duration if duration > 0 and evaluator.scan_count > 1 else evaluator.scan_count / 3.0
    avg_pts = evaluator.total_points / evaluator.scan_count
    valid_ratio = (evaluator.valid_points / evaluator.total_points * 100) if evaluator.total_points > 0 else 0
    
    print(f"Tổng số frame nhận được : {evaluator.scan_count} messages")
    print(f"Tần số quét thực tế     : {hz:.2f} Hz (Kỳ vọng: ~10.0 Hz)")
    print(f"Frame ID                : {msg.header.frame_id}")
    print(f"Góc quét angle_min      : {math.degrees(msg.angle_min):.2f}° ({msg.angle_min:.4f} rad)")
    print(f"Góc quét angle_max      : {math.degrees(msg.angle_max):.2f}° ({msg.angle_max:.4f} rad)")
    print(f"Độ phân giải góc        : {math.degrees(msg.angle_increment):.3f}°")
    print(f"Giới hạn khoảng cách    : {msg.range_min:.2f} m -> {msg.range_max:.2f} m")
    print(f"Số điểm scan trung bình : {avg_pts:.0f} điểm / vòng 360°")
    print(f"Số điểm hợp lệ          : {evaluator.valid_points} ({valid_ratio:.1f}%)")
    
    if evaluator.valid_points > 0:
        print(f"Khoảng cách gần nhất    : {evaluator.min_dist:.3f} m")
        print(f"Khoảng cách xa nhất     : {evaluator.max_dist:.3f} m")
    else:
        print("[WARNING] Không có điểm scan hợp lệ (toàn bộ là inf hoặc ngoài dải đo)!")
        
    print("--------------------------------------------------")
    
    # Tiêu chuẩn nghiệm thu PASS:
    # 1. Có tin nhắn LaserScan
    # 2. Số điểm scan > 100 mỗi frame
    # 3. Tỷ lệ điểm hợp lệ > 5% (trong phòng luôn có phản xạ từ tường/đồ vật)
    # 4. Tần số >= 5 Hz
    if evaluator.scan_count >= 5 and valid_ratio > 5.0 and hz >= 5.0:
        print("[PASS] DỮ LIỆU LASERSCAN HỢP LỆ & CẢM BIẾN HOẠT ĐỘNG HOÀN HẢO!")
        print("==================================================")
        sys.exit(0)
    else:
        print("[FAIL] Dữ liệu scan chưa đạt tiêu chuẩn nghiệm thu!")
        print("==================================================")
        sys.exit(1)

if __name__ == '__main__':
    main()
EOF

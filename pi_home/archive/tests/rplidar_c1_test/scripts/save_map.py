#!/usr/bin/env python3
# ==============================================================================
# save_map.py - Script Python gọi service /slam_toolbox/save_map an toàn
# ==============================================================================

import os
import sys
import time
import rclpy
from rclpy.node import Node
from slam_toolbox.srv import SaveMap
from std_msgs.msg import String

def main():
    map_name = sys.argv[1] if len(sys.argv) > 1 else f"map_{time.strftime('%Y%m%d_%H%M%S')}"
    target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "maps"))
    os.makedirs(target_dir, exist_ok=True)
    target_base = os.path.join(target_dir, map_name)

    print("==================================================")
    print("            LƯU BẢN ĐỒ SLAM TOOLBOX 2D            ")
    print("==================================================")
    print(f"  -> Tên bản đồ   : {map_name}")
    print(f"  -> Đường dẫn    : {target_base}")

    rclpy.init()
    node = Node("map_saver_client")
    client = node.create_client(SaveMap, "/slam_toolbox/save_map")

    if not client.wait_for_service(timeout_sec=4.0):
        print("[FAIL] Service /slam_toolbox/save_map không khả dụng! Đảm bảo SLAM Toolbox đang chạy.")
        rclpy.shutdown()
        sys.exit(1)

    req = SaveMap.Request()
    str_msg = String()
    str_msg.data = target_base
    req.name = str_msg

    future = client.call_async(req)
    rclpy.spin_until_future_complete(node, future, timeout_sec=6.0)

    if future.done():
        res = future.result()
        print(f"  -> Mã phản hồi Service: {res.result} (0: Thành công, 1: Chưa nhận map, 255: Lỗi không xác định)")
        
        # Nếu service thành công, chờ ghi file
        time.sleep(1)
        yaml_file = f"{target_base}.yaml"
        pgm_file = f"{target_base}.pgm"

        # Nếu service chưa xuất được file (ví dụ do mode permissions hoặc path), dùng nav2_map_server map_saver_cli
        if not (os.path.exists(yaml_file) or os.path.exists(pgm_file)):
            print("  -> Chạy bổ trợ nav2_map_server map_saver_cli...")
            import subprocess
            cmd = f"source /opt/ros/jazzy/setup.bash && ros2 run nav2_map_server map_saver_cli -f '{target_base}'"
            subprocess.run(["bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            time.sleep(1)

        if os.path.exists(yaml_file) or os.path.exists(pgm_file):
            print("[PASS] BẢN ĐỒ ĐÃ ĐƯỢC LƯU THÀNH CÔNG!")
            if os.path.exists(yaml_file):
                print(f"  - File Metadata : {yaml_file}")
            if os.path.exists(pgm_file):
                print(f"  - File Hình ảnh : {pgm_file} ({os.path.getsize(pgm_file):,} bytes)")
            print("==================================================")
            rclpy.shutdown()
            sys.exit(0)
        else:
            print(f"[FAIL] Không thể lưu file bản đồ tại {target_base}")
            rclpy.shutdown()
            sys.exit(1)
    else:
        print("[FAIL] Gọi service /slam_toolbox/save_map bị hết thời gian chờ!")
        rclpy.shutdown()
        sys.exit(1)

if __name__ == "__main__":
    main()

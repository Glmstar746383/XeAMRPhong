#!/usr/bin/env python3
# ==============================================================================
# system_check.py - Module thực hiện 9 bước kiểm tra toàn diện hệ thống
# ==============================================================================

import os
import sys
import platform
import subprocess
import glob

class SystemChecker:
    def __init__(self, workspace_path=None):
        self.workspace_path = workspace_path or os.path.expanduser("~/rplidar_c1_ws")
        self.results = []

    def run_command(self, cmd, shell=True):
        try:
            res = subprocess.run(
                cmd,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            return res.returncode == 0, res.stdout.strip(), res.stderr.strip()
        except Exception as e:
            return False, "", str(e)

    def check_all(self):
        self.results = []
        
        # STEP 1: Kiểm tra OS
        os_name = platform.system()
        distro = "Unknown"
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        distro = line.split("=", 1)[1].strip('"\n')
                        break
        if os_name == "Linux":
            self.results.append({
                "step": 1,
                "title": "Hệ điều hành (OS)",
                "status": "PASS",
                "detail": f"{distro} ({os_name})"
            })
        else:
            self.results.append({
                "step": 1,
                "title": "Hệ điều hành (OS)",
                "status": "WARNING",
                "detail": f"{os_name} (Khuyến nghị chạy trực tiếp trên Linux Raspberry Pi)"
            })

        # STEP 2: Kiểm tra Architecture
        arch = platform.machine()
        if arch in ["aarch64", "armv7l", "x86_64"]:
            self.results.append({
                "step": 2,
                "title": "Kiến trúc CPU (Architecture)",
                "status": "PASS",
                "detail": f"{arch}"
            })
        else:
            self.results.append({
                "step": 2,
                "title": "Kiến trúc CPU (Architecture)",
                "status": "WARNING",
                "detail": f"Kiến trúc không phổ biến: {arch}"
            })

        # STEP 3: Kiểm tra ROS2
        ros_distro = os.environ.get("ROS_DISTRO", "")
        if not ros_distro:
            # Thử tìm trong /opt/ros
            opt_ros = glob.glob("/opt/ros/*")
            if opt_ros:
                ros_distro = os.path.basename(opt_ros[0])
        
        if ros_distro:
            self.results.append({
                "step": 3,
                "title": "Môi trường ROS 2",
                "status": "PASS",
                "detail": f"ROS 2 {ros_distro.capitalize()} (/opt/ros/{ros_distro})"
            })
        else:
            self.results.append({
                "step": 3,
                "title": "Môi trường ROS 2",
                "status": "FAIL",
                "detail": "Không tìm thấy ROS 2 trong môi trường hoặc /opt/ros/."
            })

        # STEP 4: Kiểm tra Workspace / Driver
        ws_found = False
        ws_path_used = ""
        for ws in [self.workspace_path, os.path.expanduser("~/robot_ws")]:
            if os.path.exists(os.path.join(ws, "install", "setup.bash")):
                ws_found = True
                ws_path_used = ws
                break
        
        if ws_found:
            self.results.append({
                "step": 4,
                "title": "ROS 2 Workspace",
                "status": "PASS",
                "detail": f"Đã build tại: {ws_path_used}"
            })
        else:
            self.results.append({
                "step": 4,
                "title": "ROS 2 Workspace",
                "status": "WARNING",
                "detail": "Chưa thấy install/setup.bash. Chạy ./scripts/install_dependencies.sh."
            })

        # STEP 5: Kiểm tra USB kết nối C1
        ok, lsusb_out, _ = self.run_command("lsusb")
        c1_usb_found = False
        if ok:
            if "10c4:ea60" in lsusb_out or "CP210" in lsusb_out or "Silicon Labs" in lsusb_out:
                c1_usb_found = True
        
        if c1_usb_found:
            self.results.append({
                "step": 5,
                "title": "Phần cứng USB RPLIDAR",
                "status": "PASS",
                "detail": "Phát hiện Silicon Labs CP210x (VID: 10c4, PID: ea60)"
            })
        else:
            self.results.append({
                "step": 5,
                "title": "Phần cứng USB RPLIDAR",
                "status": "FAIL",
                "detail": "Không thấy adapter CP210x trên bus USB qua lệnh lsusb."
            })

        # STEP 6: Tìm Serial Device
        serial_port = None
        # Ưu tiên symlink /dev/rplidar_c1
        if os.path.exists("/dev/rplidar_c1"):
            serial_port = "/dev/rplidar_c1"
        elif os.path.exists("/dev/serial/by-id"):
            for dev in glob.glob("/dev/serial/by-id/*"):
                if "CP210" in dev or "Silicon_Labs" in dev or "10c4" in dev:
                    serial_port = dev
                    break
        if not serial_port and glob.glob("/dev/ttyUSB*"):
            serial_port = glob.glob("/dev/ttyUSB*")[0]

        if serial_port:
            real_path = os.path.realpath(serial_port)
            self.results.append({
                "step": 6,
                "title": "Cổng Serial Thiết bị",
                "status": "PASS",
                "detail": f"{serial_port} -> {real_path}"
            })
        else:
            self.results.append({
                "step": 6,
                "title": "Cổng Serial Thiết bị",
                "status": "FAIL",
                "detail": "Không phát hiện cổng /dev/ttyUSB*, /dev/serial/by-id hoặc /dev/rplidar_c1."
            })

        # STEP 7: Kiểm tra Quyền Serial (Permission)
        if serial_port:
            real_path = os.path.realpath(serial_port)
            readable = os.access(real_path, os.R_OK)
            writable = os.access(real_path, os.W_OK)
            if readable and writable:
                self.results.append({
                    "step": 7,
                    "title": "Quyền Truy Cập Serial",
                    "status": "PASS",
                    "detail": "Người dùng hiện tại có đủ quyền Đọc/Ghi (Read/Write OK)"
                })
            else:
                self.results.append({
                    "step": 7,
                    "title": "Quyền Truy Cập Serial",
                    "status": "FAIL",
                    "detail": f"Thiếu quyền truy cập vào {real_path}! Hãy chạy ./scripts/setup_udev.sh."
                })
        else:
            self.results.append({
                "step": 7,
                "title": "Quyền Truy Cập Serial",
                "status": "FAIL",
                "detail": "Không thể kiểm tra quyền vì chưa tìm thấy cổng Serial."
            })

        # STEP 8: Kiểm tra Package sllidar_ros2
        check_pkg_cmd = f"bash -l -c 'source /opt/ros/{ros_distro}/setup.bash 2>/dev/null; " \
                        f"source {ws_path_used}/install/setup.bash 2>/dev/null; " \
                        f"ros2 pkg prefix sllidar_ros2'"
        ok, pkg_out, _ = self.run_command(check_pkg_cmd)
        if ok and "sllidar_ros2" in pkg_out:
            self.results.append({
                "step": 8,
                "title": "Package sllidar_ros2",
                "status": "PASS",
                "detail": f"Đã định vị: {pkg_out}"
            })
        else:
            self.results.append({
                "step": 8,
                "title": "Package sllidar_ros2",
                "status": "FAIL",
                "detail": "Không tìm thấy package sllidar_ros2. Cần chạy install_dependencies.sh."
            })

        # STEP 9: Kiểm tra RViz2
        rviz_bin = f"/opt/ros/{ros_distro}/bin/rviz2"
        if os.path.exists(rviz_bin):
            self.results.append({
                "step": 9,
                "title": "Ứng dụng RViz2",
                "status": "PASS",
                "detail": f"RViz2 đã sẵn sàng: {rviz_bin}"
            })
        else:
            check_rviz_cmd = f"bash -c 'source /opt/ros/{ros_distro}/setup.bash 2>/dev/null && which rviz2'"
            ok, rviz_out, _ = self.run_command(check_rviz_cmd)
            if ok and "rviz2" in rviz_out:
                self.results.append({
                    "step": 9,
                    "title": "Ứng dụng RViz2",
                    "status": "PASS",
                    "detail": f"RViz2 đã sẵn sàng: {rviz_out}"
                })
            else:
                self.results.append({
                    "step": 9,
                    "title": "Ứng dụng RViz2",
                    "status": "WARNING",
                    "detail": "Chưa tìm thấy rviz2. Cần cài: sudo apt install ros-<distro>-rviz2."
                })

        return self.results

if __name__ == "__main__":
    checker = SystemChecker()
    results = checker.check_all()
    print("==================================================")
    print("         KẾT QUẢ KIỂM TRA HỆ THỐNG (9 BƯỚC)       ")
    print("==================================================")
    all_pass = True
    for r in results:
        status_tag = f"[{r['status']}]"
        print(f"STEP {r['step']}: {status_tag:<9} {r['title']}")
        print(f"       -> {r['detail']}")
        if r['status'] == 'FAIL':
            all_pass = False
    print("==================================================")
    if all_pass:
        print("TỔNG QUAN: TẤT CẢ CÁC TIÊU CHÍ ĐÃ ĐẠT (PASS)!")
    else:
        print("TỔNG QUAN: CÓ MỤC CẦN KHẮC PHỤC (FAIL/WARNING)!")

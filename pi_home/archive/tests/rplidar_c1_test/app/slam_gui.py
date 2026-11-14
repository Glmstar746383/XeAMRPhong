#!/usr/bin/env python3
# ==============================================================================
# slam_gui.py - Ứng dụng SLAM CONTROL GUI (Tkinter) cho RPLIDAR C1
# ==============================================================================

import os
import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import subprocess

# Nạp sys.path
sys.path.insert(0, os.path.dirname(__file__))

from lidar_manager import LidarManager
from ros_manager import RosManager
from slam_manager import SlamManager
from odom_monitor import OdomMonitor
from tf_monitor import TfMonitor

class SlamControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RPLIDAR C1 - SLAM CONTROL & 2D MAPPING")
        self.root.geometry("860x780")
        self.root.minsize(800, 720)

        self.lidar_mgr = LidarManager()
        self.ros_mgr = RosManager()
        self.slam_mgr = SlamManager()
        self.odom_mon = OdomMonitor()
        self.tf_mon = TfMonitor()

        self.ros_mgr.start_monitoring()
        self.slam_mgr.start_map_listener()
        self.odom_mon.start_monitoring()

        self._setup_style()
        self._create_widgets()

        # Vòng lặp cập nhật giao diện định kỳ 500ms
        self.root.after(500, self._periodic_update)

    def _setup_style(self):
        self.COLOR_BG = "#1e222b"
        self.COLOR_PANEL = "#282c37"
        self.COLOR_TEXT = "#e1e4ea"
        self.COLOR_MUTED = "#8b949e"
        self.COLOR_PASS = "#2ea043"
        self.COLOR_FAIL = "#da3633"
        self.COLOR_WARN = "#d29922"
        self.COLOR_INFO = "#58a6ff"

        self.root.configure(bg=self.COLOR_BG)

    def _create_widgets(self):
        # 1. HEADER
        header_frame = tk.Frame(self.root, bg="#161b22", pady=12, padx=16)
        header_frame.pack(fill="x")

        title_label = tk.Label(
            header_frame,
            text="RPLIDAR C1 + ROS 2 + SLAM TOOLBOX",
            font=("Helvetica", 16, "bold"),
            fg="#58a6ff",
            bg="#161b22"
        )
        title_label.pack(anchor="w")

        subtitle_label = tk.Label(
            header_frame,
            text="Hệ thống tạo bản đồ 2D Realtime bằng thuật toán SLAM Karto / Ceres Solver",
            font=("Helvetica", 10),
            fg=self.COLOR_MUTED,
            bg="#161b22"
        )
        subtitle_label.pack(anchor="w")

        # 2. STATUS SUMMARY BANNER
        self.banner_frame = tk.Frame(self.root, bg="#21262d", pady=8)
        self.banner_frame.pack(fill="x", padx=14, pady=8)

        self.lbl_status = tk.Label(
            self.banner_frame,
            text="TRẠNG THÁI: SẴN SÀNG (CHƯA KHỞI ĐỘNG)",
            font=("Helvetica", 12, "bold"),
            fg="#c9d1d9",
            bg="#21262d"
        )
        self.lbl_status.pack()

        # 3. DASHBOARD GRIDS (Trạng Thái + Chỉ Số Đo)
        dash_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        dash_frame.pack(fill="x", padx=14, pady=4)
        dash_frame.columnconfigure(0, weight=1)
        dash_frame.columnconfigure(1, weight=1)

        # Panel 1: Trạng Thái 6 Thành Phần Cốt Lõi
        p1 = tk.LabelFrame(
            dash_frame, text=" 1. Các Khối Hệ Thống ", fg="#58a6ff",
            bg=self.COLOR_PANEL, font=("Helvetica", 10, "bold"), padx=10, pady=8
        )
        p1.grid(row=0, column=0, sticky="nsew", padx=4)

        self.led_lidar = self._create_led_row(p1, "RPLIDAR C1 Sensor:")
        self.led_scan = self._create_led_row(p1, "Topic /scan (LaserScan):")
        self.led_odom = self._create_led_row(p1, "Wheel Odometry (/odom):")
        self.led_tf = self._create_led_row(p1, "TF Tree (map->odom->base->laser):")
        self.led_slam = self._create_led_row(p1, "SLAM Toolbox Node:")
        self.led_map = self._create_led_row(p1, "Topic /map (OccupancyGrid):")

        # Panel 2: Chỉ Số Đo Realtime
        p2 = tk.LabelFrame(
            dash_frame, text=" 2. Thông Số Hoạt Động ", fg="#58a6ff",
            bg=self.COLOR_PANEL, font=("Helvetica", 10, "bold"), padx=10, pady=8
        )
        p2.grid(row=0, column=1, sticky="nsew", padx=4)

        self.lbl_scan_hz = tk.Label(p2, text="Tần số LiDAR     : 0.00 Hz", font=("Helvetica", 9), fg=self.COLOR_TEXT, bg=self.COLOR_PANEL)
        self.lbl_scan_hz.pack(anchor="w", pady=2)

        self.lbl_odom_hz = tk.Label(p2, text="Tần số Odometry  : 0.00 Hz", font=("Helvetica", 9), fg=self.COLOR_TEXT, bg=self.COLOR_PANEL)
        self.lbl_odom_hz.pack(anchor="w", pady=2)

        self.lbl_map_dim = tk.Label(p2, text="Kích thước bản đồ: 0.0 x 0.0 mét", font=("Helvetica", 9), fg=self.COLOR_TEXT, bg=self.COLOR_PANEL)
        self.lbl_map_dim.pack(anchor="w", pady=2)

        self.lbl_map_cells = tk.Label(p2, text="Số ô lưới (Cells): 0 ô (Độ phân giải: 5cm)", font=("Helvetica", 9), fg=self.COLOR_TEXT, bg=self.COLOR_PANEL)
        self.lbl_map_cells.pack(anchor="w", pady=2)

        self.lbl_mode = tk.Label(p2, text="Chế độ chạy      : Pi + RPLIDAR C1", font=("Helvetica", 9, "bold"), fg=self.COLOR_INFO, bg=self.COLOR_PANEL)
        self.lbl_mode.pack(anchor="w", pady=2)

        # 4. ACTION BUTTONS
        btn_frame = tk.Frame(self.root, bg=self.COLOR_BG, pady=8)
        btn_frame.pack(fill="x", padx=14)

        btn_style = {"font": ("Helvetica", 9, "bold"), "padx": 8, "pady": 6, "relief": "flat", "cursor": "hand2"}

        self.btn_check = tk.Button(
            btn_frame, text="🔍 CHECK SYSTEM", bg="#1f6feb", fg="white",
            command=self.on_check_system, **btn_style
        )
        self.btn_check.pack(side="left", padx=3)

        self.btn_start = tk.Button(
            btn_frame, text="▶ START MAPPING", bg="#238636", fg="white",
            command=self.on_start_mapping, **btn_style
        )
        self.btn_start.pack(side="left", padx=3)

        self.btn_view = tk.Button(
            btn_frame, text="👁 VIEW MAP (RViz2)", bg="#8957e5", fg="white",
            command=self.on_view_map, **btn_style
        )
        self.btn_view.pack(side="left", padx=3)

        self.btn_save = tk.Button(
            btn_frame, text="💾 SAVE MAP", bg="#388bfd", fg="white",
            command=self.on_save_map, **btn_style
        )
        self.btn_save.pack(side="left", padx=3)

        self.btn_reset = tk.Button(
            btn_frame, text="🔄 RESET MAP", bg="#d29922", fg="white",
            command=self.on_reset_map, **btn_style
        )
        self.btn_reset.pack(side="left", padx=3)

        self.btn_stop = tk.Button(
            btn_frame, text="⏹ STOP", bg="#da3633", fg="white",
            command=self.on_stop, **btn_style
        )
        self.btn_stop.pack(side="right", padx=3)

        # 5. LOG CONSOLE
        log_frame = tk.LabelFrame(
            self.root, text=" Nhật Ký SLAM & Báo Cáo Hệ Thống ", fg="#58a6ff",
            bg=self.COLOR_PANEL, font=("Helvetica", 10, "bold"), padx=8, pady=6
        )
        log_frame.pack(fill="both", expand=True, padx=14, pady=6)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap="word",
            bg="#0d1117",
            fg="#c9d1d9",
            font=("Consolas", 9),
            insertbackground="white"
        )
        self.log_text.pack(fill="both", expand=True)

        self._log("Chào mừng bạn đến với SLAM CONTROL TOOL (RPLIDAR C1 + SLAM Toolbox)!")
        self._log("Hệ thống kiểm tra ở mức độ Raspberry Pi + RPLIDAR C1.")
        self._log("Bấm [ CHECK SYSTEM ] hoặc [ START MAPPING ] để bắt đầu tạo bản đồ.\n")

    def _create_led_row(self, parent, text):
        f = tk.Frame(parent, bg=self.COLOR_PANEL)
        f.pack(fill="x", pady=2)
        led = tk.Label(f, text="●", font=("Helvetica", 12), fg=self.COLOR_MUTED, bg=self.COLOR_PANEL)
        led.pack(side="left", padx=(0, 4))
        lbl = tk.Label(f, text=text, font=("Helvetica", 9), fg=self.COLOR_TEXT, bg=self.COLOR_PANEL)
        lbl.pack(side="left")
        return led

    def _set_led(self, led, status):
        colors = {"PASS": self.COLOR_PASS, "FAIL": self.COLOR_FAIL, "WARN": self.COLOR_WARN, "OFF": self.COLOR_MUTED}
        led.config(fg=colors.get(status, self.COLOR_MUTED))

    def _log(self, message):
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def on_check_system(self):
        self._log("\n" + "="*50)
        self._log("ĐANG KIỂM TRA ĐIỀU KIỆN TẠO BẢN ĐỒ SLAM...")
        self.btn_check.config(state="disabled")

        def run():
            check_script = os.path.join(self.slam_mgr.root_dir, "scripts", "check_slam.sh")
            res = subprocess.run(["bash", check_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            def update():
                self._log(res.stdout)
                self.btn_check.config(state="normal")
            self.root.after(0, update)

        threading.Thread(target=run, daemon=True).start()

    def on_start_mapping(self):
        self._log("\nĐang khởi chạy SLAM Toolbox...")
        self.btn_start.config(state="disabled")

        def run():
            ok, msg = self.slam_mgr.start_slam()
            def update():
                self._log(msg)
                if ok:
                    self._update_status("RUNNING", "SLAM ĐANG TẠO BẢN ĐỒ REALTIME (CHẾ ĐỘ PI + C1)")
                else:
                    self._update_status("FAIL", "LỖI KHỞI ĐỘNG SLAM TOOLBOX")
                self.btn_start.config(state="normal")
            self.root.after(0, update)

        threading.Thread(target=run, daemon=True).start()

    def on_view_map(self):
        self._log("\nĐang mở RViz2 hiển thị bản đồ...")
        ok, msg = self.slam_mgr.start_rviz()
        self._log(msg)

    def on_save_map(self):
        self._log("\nĐang lưu bản đồ vào thư mục maps/...")
        def run():
            ok, msg = self.slam_mgr.save_map()
            def update():
                self._log(msg)
                if ok:
                    messagebox.showinfo("Lưu Bản Đồ", "Bản đồ đã được lưu thành công vào thư mục maps/!")
                else:
                    messagebox.showwarning("Lỗi Lưu Map", "Chưa thể lưu bản đồ. Hãy đảm bảo SLAM đã tạo ra bản đồ!")
            self.root.after(0, update)
        threading.Thread(target=run, daemon=True).start()

    def on_reset_map(self):
        if messagebox.askyesno("Xác Nhận Reset", "Bạn có chắc chắn muốn xóa bản đồ hiện tại để vẽ lại từ đầu không?"):
            self._log("\nĐang gửi yêu cầu Reset phiên bản đồ hiện tại...")
            ok, msg = self.slam_mgr.reset_map()
            self._log(msg)

    def on_stop(self):
        self._log("\nĐang dừng SLAM Toolbox...")
        ok, msg = self.slam_mgr.stop_slam()
        self._log(msg)
        self._update_status("OFF", "TRẠNG THÁI: SLAM ĐÃ DỪNG AN TOÀN")

    def _periodic_update(self):
        # 1. Cập nhật trạng thái LiDAR
        lidar_alive = self.lidar_mgr.is_running()
        self._set_led(self.led_lidar, "PASS" if lidar_alive else "OFF")

        # 2. Cập nhật topic /scan
        scan_stats = self.ros_mgr.get_stats()
        scan_receiving = scan_stats["receiving"]
        self._set_led(self.led_scan, "PASS" if scan_receiving else "OFF")
        self.lbl_scan_hz.config(text=f"Tần số LiDAR     : {scan_stats['hz']:.2f} Hz")

        # 3. Cập nhật Odometry
        odom_stats = self.odom_mon.get_status()
        if odom_stats["active"]:
            self._set_led(self.led_odom, "PASS")
            self.lbl_odom_hz.config(text=f"Tần số Odometry  : {odom_stats['hz']:.2f} Hz")
        else:
            self._set_led(self.led_odom, "WARN")
            self.lbl_odom_hz.config(text="Tần số Odometry  : 0.00 Hz (Pi+LiDAR Mode)")

        # 4. Cập nhật SLAM & Map
        slam_running = self.slam_mgr.is_running()
        self._set_led(self.led_slam, "PASS" if slam_running else "OFF")

        map_stats = self.slam_mgr.get_map_stats()
        if map_stats["active"]:
            self._set_led(self.led_map, "PASS")
            self.lbl_map_dim.config(text=f"Kích thước bản đồ: {map_stats['width_m']:.1f} x {map_stats['height_m']:.1f} mét")
            self.lbl_map_cells.config(text=f"Số ô lưới (Cells): {map_stats['cells']:,} ô (Độ phân giải: {map_stats['resolution']*100:.0f}cm)")
        else:
            self._set_led(self.led_map, "OFF")
            if not slam_running:
                self.lbl_map_dim.config(text="Kích thước bản đồ: 0.0 x 0.0 mét")
                self.lbl_map_cells.config(text="Số ô lưới (Cells): 0 ô")

        # TF Tree status
        if slam_running and map_stats["active"]:
            self._set_led(self.led_tf, "PASS")
        elif lidar_alive:
            self._set_led(self.led_tf, "WARN")
        else:
            self._set_led(self.led_tf, "OFF")

        self.root.after(500, self._periodic_update)

    def _update_status(self, mode, text):
        colors = {
            "RUNNING": (self.COLOR_PASS, "#ffffff"),
            "FAIL": (self.COLOR_FAIL, "#ffffff"),
            "OFF": ("#30363d", "#c9d1d9"),
        }
        bg, fg = colors.get(mode, ("#21262d", "#c9d1d9"))
        self.banner_frame.config(bg=bg)
        self.lbl_status.config(text=text, bg=bg, fg=fg)

def main():
    root = tk.Tk()
    app = SlamControlApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

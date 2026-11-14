#!/usr/bin/env python3
# ==============================================================================
# main.py - Ứng dụng GUI kiểm thử cảm biến RPLIDAR C1M1 trên Raspberry Pi
# Sử dụng Tkinter trực quan, gọn nhẹ, đầy đủ trạng thái và nút bấm chức năng.
# ==============================================================================

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import subprocess

# Bổ sung thư mục app vào sys.path
sys.path.insert(0, os.path.dirname(__file__))

from system_check import SystemChecker
from lidar_manager import LidarManager
from ros_manager import RosManager

class RplidarC1TestApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RPLIDAR C1M1 360° Laser Range Scanner - Test Tool")
        self.root.geometry("820x720")
        self.root.minsize(780, 680)

        self.lidar_manager = LidarManager()
        self.ros_manager = RosManager()
        self.ros_manager.start_monitoring()

        self._setup_style()
        self._create_widgets()
        
        # Bắt đầu vòng lặp cập nhật trạng thái GUI định kỳ (500ms)
        self.root.after(500, self._periodic_update)

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Cấu hình màu sắc
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
            text="RPLIDAR C1M1 360° SENSOR TEST TOOL",
            font=("Helvetica", 16, "bold"),
            fg="#58a6ff",
            bg="#161b22"
        )
        title_label.pack(anchor="w")

        subtitle_label = tk.Label(
            header_frame,
            text="Công cụ kiểm tra phần cứng, driver sllidar_ros2, topic /scan và hiển thị RViz2",
            font=("Helvetica", 10),
            fg=self.COLOR_MUTED,
            bg="#161b22"
        )
        subtitle_label.pack(anchor="w")

        # 2. STATUS SUMMARY BANNER
        self.banner_frame = tk.Frame(self.root, bg="#21262d", pady=8)
        self.banner_frame.pack(fill="x", padx=14, pady=8)
        
        self.lbl_overall = tk.Label(
            self.banner_frame,
            text="TRẠNG THÁI: SẴN SÀNG (CHƯA TEST)",
            font=("Helvetica", 13, "bold"),
            fg="#c9d1d9",
            bg="#21262d"
        )
        self.lbl_overall.pack()

        # 3. MAIN DASHBOARD GRIDS
        dash_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        dash_frame.pack(fill="x", padx=14, pady=4)
        dash_frame.columnconfigure(0, weight=1)
        dash_frame.columnconfigure(1, weight=1)
        dash_frame.columnconfigure(2, weight=1)

        # Panel 1: Kết Nối Cảm Biến
        p1 = tk.LabelFrame(dash_frame, text=" 1. Kết Nối Cảm Biến ", fg="#58a6ff", bg=self.COLOR_PANEL, font=("Helvetica", 10, "bold"), padx=10, pady=8)
        p1.grid(row=0, column=0, sticky="nsew", padx=4)

        self.led_usb = self._create_led_row(p1, "USB Device (CP210x):")
        self.led_perm = self._create_led_row(p1, "Quyền Serial Port:")
        self.lbl_port = tk.Label(p1, text="Cổng: /dev/...", font=("Helvetica", 8), fg=self.COLOR_MUTED, bg=self.COLOR_PANEL)
        self.lbl_port.pack(anchor="w", pady=(4, 0))

        # Panel 2: Hệ Thống ROS 2
        p2 = tk.LabelFrame(dash_frame, text=" 2. ROS 2 & Driver ", fg="#58a6ff", bg=self.COLOR_PANEL, font=("Helvetica", 10, "bold"), padx=10, pady=8)
        p2.grid(row=0, column=1, sticky="nsew", padx=4)

        self.led_ros = self._create_led_row(p2, "ROS 2 Environment:")
        self.led_driver = self._create_led_row(p2, "Driver C1 (Running):")
        self.led_topic = self._create_led_row(p2, "Topic /scan (Active):")

        # Panel 3: Dữ Liệu Quét Thực Tế
        p3 = tk.LabelFrame(dash_frame, text=" 3. Dữ Liệu Quét 360° ", fg="#58a6ff", bg=self.COLOR_PANEL, font=("Helvetica", 10, "bold"), padx=10, pady=8)
        p3.grid(row=0, column=2, sticky="nsew", padx=4)

        self.lbl_hz = tk.Label(p3, text="Tần số: 0.00 Hz", font=("Helvetica", 9), fg=self.COLOR_TEXT, bg=self.COLOR_PANEL)
        self.lbl_hz.pack(anchor="w", pady=1)

        self.lbl_valid = tk.Label(p3, text="Điểm hợp lệ: 0 / 0 (0%)", font=("Helvetica", 9), fg=self.COLOR_TEXT, bg=self.COLOR_PANEL)
        self.lbl_valid.pack(anchor="w", pady=1)

        self.lbl_range = tk.Label(p3, text="Khoảng cách: 0.00m - 0.00m", font=("Helvetica", 9), fg=self.COLOR_TEXT, bg=self.COLOR_PANEL)
        self.lbl_range.pack(anchor="w", pady=1)

        # 4. ACTION BUTTONS
        btn_frame = tk.Frame(self.root, bg=self.COLOR_BG, pady=8)
        btn_frame.pack(fill="x", padx=14)

        btn_style = {"font": ("Helvetica", 10, "bold"), "padx": 10, "pady": 6, "relief": "flat", "cursor": "hand2"}

        self.btn_check = tk.Button(
            btn_frame, text="🔍 CHECK SYSTEM", bg="#1f6feb", fg="white",
            command=self.on_check_system, **btn_style
        )
        self.btn_check.pack(side="left", padx=4)

        self.btn_start = tk.Button(
            btn_frame, text="▶ START LIDAR", bg="#238636", fg="white",
            command=self.on_start_lidar, **btn_style
        )
        self.btn_start.pack(side="left", padx=4)

        self.btn_view = tk.Button(
            btn_frame, text="👁 VIEW SCAN (RViz2)", bg="#8957e5", fg="white",
            command=self.on_view_scan, **btn_style
        )
        self.btn_view.pack(side="left", padx=4)

        self.btn_stop = tk.Button(
            btn_frame, text="⏹ STOP LIDAR", bg="#da3633", fg="white",
            command=self.on_stop_lidar, **btn_style
        )
        self.btn_stop.pack(side="left", padx=4)

        self.btn_diag = tk.Button(
            btn_frame, text="📋 DIAGNOSTICS", bg="#30363d", fg="#c9d1d9",
            command=self.on_diagnostics, **btn_style
        )
        self.btn_diag.pack(side="right", padx=4)

        # 5. LOG CONSOLE & SYSTEM RESULTS
        log_frame = tk.LabelFrame(
            self.root, text=" Nhật Ký Kiểm Tra & Hoạt Động ", fg="#58a6ff",
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

        self._log("Chào mừng bạn đến với RPLIDAR C1 Test Tool!")
        self._log("Bấm [ CHECK SYSTEM ] để bắt đầu kiểm tra cấu hình hệ thống.\n")

    def _create_led_row(self, parent, text):
        f = tk.Frame(parent, bg=self.COLOR_PANEL)
        f.pack(fill="x", pady=2)
        
        led = tk.Label(f, text="●", font=("Helvetica", 12), fg=self.COLOR_MUTED, bg=self.COLOR_PANEL)
        led.pack(side="left", padx=(0, 4))
        
        lbl = tk.Label(f, text=text, font=("Helvetica", 9), fg=self.COLOR_TEXT, bg=self.COLOR_PANEL)
        lbl.pack(side="left")
        
        return led

    def _set_led(self, led_widget, status):
        # status: PASS (Green), FAIL (Red), WARN (Yellow), OFF (Gray)
        colors = {
            "PASS": self.COLOR_PASS,
            "FAIL": self.COLOR_FAIL,
            "WARN": self.COLOR_WARN,
            "OFF": self.COLOR_MUTED
        }
        led_widget.config(fg=colors.get(status, self.COLOR_MUTED))

    def _log(self, message):
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def on_check_system(self):
        self._log("\n" + "="*50)
        self._log("BẮT ĐẦU KIỂM TRA HỆ THỐNG 9 BƯỚC...")
        self.btn_check.config(state="disabled")
        
        def run():
            checker = SystemChecker()
            results = checker.check_all()
            
            all_pass = True
            for r in results:
                stat = r["status"]
                self._log(f"[{stat}] BƯỚC {r['step']}: {r['title']}")
                self._log(f"       -> {r['detail']}")
                if stat == "FAIL":
                    all_pass = False

            # Cập nhật các LED theo kết quả
            usb_ok = any(r["step"] == 5 and r["status"] == "PASS" for r in results)
            perm_ok = any(r["step"] == 7 and r["status"] == "PASS" for r in results)
            ros_ok = any(r["step"] == 3 and r["status"] == "PASS" for r in results)
            
            # Cập nhật UI từ thread chính
            self.root.after(0, lambda: self._apply_check_results(all_pass, usb_ok, perm_ok, ros_ok, results))

        threading.Thread(target=run, daemon=True).start()

    def _apply_check_results(self, all_pass, usb_ok, perm_ok, ros_ok, results):
        self._set_led(self.led_usb, "PASS" if usb_ok else "FAIL")
        self._set_led(self.led_perm, "PASS" if perm_ok else "FAIL")
        self._set_led(self.led_ros, "PASS" if ros_ok else "FAIL")
        
        # Tìm port hiển thị
        for r in results:
            if r["step"] == 6 and r["status"] == "PASS":
                self.lbl_port.config(text=f"Cổng: {r['detail'].split(' -> ')[0]}")
                break

        if all_pass:
            self._update_overall_status("PASS", "RPLIDAR C1: HỆ THỐNG ĐẠT CHUẨN (SẴN SÀNG KHỞI ĐỘNG)")
            self._log("==> KẾT QUẢ: HỆ THỐNG ĐỦ ĐIỀU KIỆN! HÃY BẤM [ START LIDAR ].")
        else:
            self._update_overall_status("FAIL", "RPLIDAR C1: PHÁT HIỆN LỖI CẤU HÌNH")
            self._log("==> KẾT QUẢ: CẦN KHẮC PHỤC CÁC MỤC FAIL Ở TRÊN TRƯỚC KHI KHỞI ĐỘNG.")

        self.btn_check.config(state="normal")

    def on_start_lidar(self):
        self._log("\nĐang khởi động driver RPLIDAR C1...")
        self.btn_start.config(state="disabled")
        
        def run():
            ok, msg = self.lidar_manager.start_lidar()
            def update():
                self._log(msg)
                if ok:
                    self._set_led(self.led_driver, "PASS")
                    self._update_overall_status("RUNNING", "RPLIDAR C1: MOTOR ĐANG QUAY & CHỜ DỮ LIỆU...")
                else:
                    self._set_led(self.led_driver, "FAIL")
                    self._update_overall_status("FAIL", "RPLIDAR C1: LỖI KHỞI ĐỘNG DRIVER")
                self.btn_start.config(state="normal")
            self.root.after(0, update)

        threading.Thread(target=run, daemon=True).start()

    def on_stop_lidar(self):
        self._log("\nĐang dừng driver và motor RPLIDAR C1...")
        ok, msg = self.lidar_manager.stop_lidar()
        self._log(msg)
        self._set_led(self.led_driver, "OFF")
        self._set_led(self.led_topic, "OFF")
        self._update_overall_status("OFF", "RPLIDAR C1: ĐÃ DỪNG AN TOÀN")

    def on_view_scan(self):
        self._log("\nĐang mở RViz2 với cấu hình chuẩn cho C1...")
        ok, msg = self.lidar_manager.start_rviz()
        self._log(msg)

    def on_diagnostics(self):
        self._log("\n" + "="*50)
        self._log("ĐANG XUẤT BÁO CÁO CHẨN ĐOÁN HỆ THỐNG...")
        
        def run():
            diag_script = os.path.join(self.lidar_manager.root_dir, "scripts", "diagnostics.sh")
            try:
                res = subprocess.run(["bash", diag_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                def update():
                    self._log(res.stdout)
                    self._log("Đã lưu chẩn đoán vào logs/diagnostics.log")
                self.root.after(0, update)
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Lỗi chạy diagnostics: {e}"))
                
        threading.Thread(target=run, daemon=True).start()

    def _periodic_update(self):
        # 1. Kiểm tra trạng thái Driver liveness
        driver_running = self.lidar_manager.is_running()
        if driver_running:
            self._set_led(self.led_driver, "PASS")
        else:
            self._set_led(self.led_driver, "OFF")

        # 2. Lấy thống kê từ ROS manager
        stats = self.ros_manager.get_stats()
        receiving = stats["receiving"]

        if receiving:
            self._set_led(self.led_topic, "PASS")
            self.lbl_hz.config(text=f"Tần số: {stats['hz']:.2f} Hz")
            self.lbl_valid.config(text=f"Điểm hợp lệ: {stats['valid_points']} / {stats['total_points']} ({stats['valid_ratio']:.1f}%)")
            self.lbl_range.config(text=f"Khoảng cách: {stats['min_dist']:.2f}m - {stats['max_dist']:.2f}m")
            
            # Nếu đang nhận dữ liệu tốt -> Báo PASS hoàn hảo
            if stats["valid_points"] > 0 and stats["hz"] >= 5.0:
                self._update_overall_status("PASS", "RPLIDAR C1: PASS (CẢM BIẾN HOẠT ĐỘNG HOÀN HẢO)")
        else:
            if driver_running:
                self._set_led(self.led_topic, "WARN")
            else:
                self._set_led(self.led_topic, "OFF")
                self.lbl_hz.config(text="Tần số: 0.00 Hz")
                self.lbl_valid.config(text="Điểm hợp lệ: 0 / 0 (0%)")
                self.lbl_range.config(text="Khoảng cách: 0.00m - 0.00m")

        # Lặp lại sau 500ms
        self.root.after(500, self._periodic_update)

    def _update_overall_status(self, mode, text):
        colors = {
            "PASS": (self.COLOR_PASS, "#ffffff"),
            "FAIL": (self.COLOR_FAIL, "#ffffff"),
            "RUNNING": (self.COLOR_INFO, "#ffffff"),
            "OFF": ("#30363d", "#c9d1d9"),
        }
        bg_col, fg_col = colors.get(mode, ("#21262d", "#c9d1d9"))
        self.banner_frame.config(bg=bg_col)
        self.lbl_overall.config(text=text, bg=bg_col, fg=fg_col)

def main():
    root = tk.Tk()
    app = RplidarC1TestApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

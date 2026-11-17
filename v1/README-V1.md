# AGV AMR — MÃ NGUỒN V1

**Ngày đóng gói:** 17/11/2026
**Trạng thái:** chạy được — 4 service active, preflight 0 FAIL
**Thiết bị:** Raspberry Pi (aarch64, 8 GB) · Ubuntu 24.04 · RPLiDAR C1 · ESP32 + MKE-M18 · Camera USB UVC

---

## 1. Đây là gì

Bản nén toàn bộ mã nguồn **V1** của xe tự hành AGV, đóng gói trước khi dọn dẹp thư mục làm việc.
Bao gồm cả checkpoint huấn luyện và các bản sao lưu, phục vụ đối chiếu về sau.

## 2. Nội dung gói

```
agv/            ứng dụng chính (brain, web UI, ROS node, AI planner)
agv-cam/        module camera (MJPEG server, node đo khoảng cách, hiệu chuẩn)
README-V1.md    tài liệu này
SHA256SUMS      mã kiểm tra toàn vẹn
```

## 3. Chức năng đang hoạt động

| Chức năng | Mô tả |
|---|---|
| SLAM | SLAM Toolbox online async, bản đồ 5 cm/ô, TF map→odom→base_footprint→laser |
| Quét mở rộng | Frontier exploration, tự về Home, báo % phủ |
| Phủ kín sàn | Dùng `models/coverage_model.onnx` chọn điểm chưa đi |
| Đi tới toạ độ | A* + bám đường, tránh vật cản bằng LiDAR |
| Đi trực tiếp A→B | Không cần bản đồ, vừa đi vừa quét |
| Tránh vật cản thấp | Camera đo khoảng cách, chặn khi < 0,30 m, ghi dấu vào bản đồ |
| Tự tìm hướng vòng | 13 hướng, lùi tạo khoảng trống khi bị vây |
| Đi về vùng trống | Khi hết frontier, tự tiến vào hướng thoáng nhất |

## 4. Cấu trúc `agv/`

### Module chạy thật

| File | Vai trò |
|---|---|
| `agv_unified_brain.py` | Não trung tâm: ROS node, web server :8080, state machine tự hành |
| `agv_command_session.py` | Giao thức serial với ESP32, quản lý ARM/STOP/telemetry |
| `agv_navigation.py` | GridPlanner, A*, frontier, inflate thân xe |
| `agv_command_journal.py` | Ghi nhật ký lệnh ra JSONL |
| `agv_ai_bridge.py` | Cầu nối 2 model ONNX |
| `agv_preflight_static_collector.py` | Thu thập chẩn đoán tĩnh, khoá cổng serial |
| `agv_speed_profile.py` | Quy đổi rpm ↔ m/s, twist ↔ bánh xe |
| `cam_avoid.py` | Lớp chặn vật cản bằng camera |

### Giao diện

| File | Đường dẫn |
|---|---|
| `index_fusion.html` | `/` — giao diện Fusion (2 tab, radar + camera) |
| `index_cyberpunk.html` | `/classic` — giao diện cũ |

### Khởi động

| File | Vai trò |
|---|---|
| `start_agv_system.sh` | `ExecStart` của `agv.service` |
| `stop_agv_system.sh` | Dừng các tiến trình con |
| `slam_scan_fix.yaml` | Tham số SLAM dự phòng |

### Model

| File | Dùng cho |
|---|---|
| `ai_local_planner/exported/local_planner.onnx` | AI 1 — né vật cản |
| `models/coverage_model.onnx` | AI 2 — phủ kín sàn |

### Công cụ

| File | Vai trò |
|---|---|
| `tools/preflight.py` | Kiểm tra tổng thể trước khi chạy |
| `tools/health_check.sh` | Tự restart khi cảm biến ngừng dữ liệu (timer 30 s) |
| `tools/power_monitor.sh` | Ghi nhiệt độ, điện áp, Wi-Fi mỗi 10 s |
| `tools/cam_avoid_selftest.py` | Kiểm thử logic tránh vật cản |

## 5. Thư mục `agv-cam/`

| File | Vai trò |
|---|---|
| `app/cam_stream.py` | MJPEG server :8081 |
| `nodes/cam_range_node.py` | Node ROS 2, phát `/cam_range`, `/cam_obstacle`, `/cam_bg_diff`, `/cam_support` |
| `nodes/cam_calib_server.py` | Web hiệu chuẩn camera |
| `calib/camera_calib.json` | Thông số hiệu chuẩn (A=54,88; v0=177,81; RMS=1,56 cm) |
| `calib/floor_ref.jpg` | Ảnh nền sàn để so sánh |

## 6. Dịch vụ hệ thống

| Service | Cổng | Ghi chú |
|---|---|---|
| `agv.service` | 8080 | WorkingDirectory `~/agv` |
| `agv-cam.service` | 8081 | `~/agv-cam/app` |
| `agv-cam-range.service` | ROS 2 | `~/agv-cam/nodes` |
| `agv-gateway.service` | 8090 | `/opt/agv-gateway` |
| `agv-monitor.service` | — | Giám sát nguồn |
| `agv-health.timer` | — | Kiểm tra 30 s/lần |

## 7. Cấu hình

Biến môi trường trong `start_agv_system.sh`:

```
AGV_BODY_RADIUS_M=0.20
AGV_BODY_BOUNDS_M=-0.155,-0.112,0.155,0.112
AGV_AUTO_SPEED_RPM=40.0
AGV_AUTO_TURN_RPM=35.0
AGV_WALL_MARGIN_M=0.00
AGV_PROGRESS_TIMEOUT_S=3.5
AGV_CAM_AVOID=1
AGV_CAM_STOP_M=0.30
AGV_CLIENT_WATCHDOG_S=2.5
```

Cấu hình lưu bền:

- `runtime/speed.json` — tốc độ đã chọn trên giao diện
- `runtime/cam_avoid.json` — ngưỡng chặn camera

## 8. Chạy lại từ gói này

```bash
tar xzf AGV-V1-20261117.tar.gz
sudo systemctl stop agv agv-cam agv-cam-range
# sao lưu bản hiện tại rồi chép đè
sudo rsync -a agv/ /home/khangho/agv/
sudo rsync -a agv-cam/ /home/khangho/agv-cam/
sudo systemctl start agv agv-cam agv-cam-range
python3 ~/agv/tools/preflight.py
```

## 9. Hạn chế đã biết (V1)

1. Bản đồ không lưu ra đĩa — restart `agv.service` là mất.
2. Camera phụ thuộc ảnh nền; đổi vị trí/ánh sáng phải chụp lại nền.
3. Vật đứng yên trong tầm nhìn lúc chụp nền sẽ không bị phát hiện.
4. LiDAR 2D có điểm mù dưới mặt phẳng quét (cao 23 cm).
5. Chế độ DIRECT không dùng bản đồ để chọn đường vòng thông minh.
6. Không tự ARM khi khởi động (cố ý, vì an toàn).
7. Raspberry Pi từng tự khởi động lại nhiều lần do mất nguồn — cần nguồn riêng cho Pi.

## 10. Lịch sử thay đổi chính

| Ngày | Nội dung |
|---|---|
| 11/11 | Hiệu chuẩn camera (pinhole-ground), dựng module agv-cam |
| 13/11 | Dọn thư mục (198→21 mục), tách module camera, thêm giao diện Fusion, git baseline |
| 14/11 | Vá camera (chọn vật gần, cân bằng sáng, bg_diff, support), chống lắc, lùi thoát kẹt, frontier 2 s, đi về vùng trống, watchdog 2,5 s + SSE, URDF, panel tốc độ, MultiThreadedExecutor |
| 17/11 | Đóng gói V1, dọn mã nguồn |

## 11. Kiểm tra toàn vẹn

```bash
sha256sum -c SHA256SUMS
```

# AGV AMR — MÃ NGUỒN V2 (bản sạch)

**Ngày:** 17/11/2026
**Nguồn:** dọn trực tiếp từ V1 sau khi đã đóng gói và lưu trữ ở `v1/`
**Kích thước:** `agv/` 7,6 MB (19 mục) · `agv-cam/` 1,2 MB

---

## 1. V2 khác V1 ở đâu

Chỉ giữ những file thực sự được dùng khi xe vận hành. Đã xoá khỏi V2:

| Đã xoá | Dung lượng |
|---|---|
| `ai_local_planner/checkpoints/` | 98 MB |
| `ai_local_planner/environments/` | 24 KB |
| `models/runs/` | 3,9 MB |
| 43 file `*.bak*` | 6,5 MB |
| `logs/command_outcomes.jsonl*` | 3,7 MB |
| `__pycache__/` | 376 KB |
| `web_tmp` | 17 KB |
| `read_events.py`, `read_outcomes.py`, `test_agv_coverage_patrol.py` | 5 KB |
| `start.sh`, `start_reboot.sh`, `launch_pi_brain.sh`, `restart_brain.sh` | 12 KB |
| `sources.sha256`, `started_once` | nhỏ |

Code không thay đổi một dòng nào — chỉ loại bỏ file không dùng.

## 2. Cấu trúc

```
agv/
├── agv_unified_brain.py              não trung tâm + web server :8080
├── agv_command_session.py            giao thức serial ESP32
├── agv_navigation.py                 A*, frontier, inflate
├── agv_command_journal.py            nhật ký lệnh
├── agv_ai_bridge.py                  cầu nối 2 model ONNX
├── agv_preflight_static_collector.py chẩn đoán, khoá cổng serial
├── agv_speed_profile.py              quy đổi rpm ↔ m/s
├── cam_avoid.py                      lớp chặn vật cản camera
├── index_fusion.html                 giao diện / (2 tab)
├── index_cyberpunk.html              giao diện /classic
├── slam_scan_fix.yaml                tham số SLAM dự phòng
├── start_agv_system.sh               ExecStart của agv.service
├── stop_agv_system.sh
├── ai_local_planner/                 __init__.py, runtime.py, exported/*.onnx
├── models/                           coverage_model.onnx + .data + .pth + manifest
├── robot/agv.urdf                    mô tả hình học
├── runtime/                          cam_avoid.json, speed.json
├── tools/                            preflight, health_check, power_monitor, selftest
└── logs/                             (tạo lại khi chạy)

agv-cam/
├── app/cam_stream.py                 MJPEG :8081
├── nodes/cam_range_node.py           ROS 2: /cam_range, /cam_obstacle, /cam_bg_diff, /cam_support
├── nodes/cam_calib_server.py         web hiệu chuẩn
└── calib/                            camera_calib.json, floor_ref.jpg
```

## 3. Triển khai lên Pi

```bash
# sao lưu bản đang chạy
sudo cp -a /home/khangho/agv /home/khangho/agv.bak_$(date +%Y%m%d_%H%M)

# chép đè
sudo rsync -a v2/agv/     /home/khangho/agv/
sudo rsync -a v2/agv-cam/ /home/khangho/agv-cam/

sudo systemctl restart agv agv-cam agv-cam-range
python3 ~/agv/tools/preflight.py
```

## 4. Cấu hình

Biến môi trường trong `start_agv_system.sh`:

```
AGV_BODY_RADIUS_M=0.20
AGV_BODY_BOUNDS_M=-0.155,-0.112,0.155,0.112
AGV_AUTO_SPEED_RPM=40.0
AGV_AUTO_TURN_RPM=35.0
AGV_CAM_STOP_M=0.30
AGV_CLIENT_WATCHDOG_S=2.5
```

Lưu bền: `runtime/speed.json`, `runtime/cam_avoid.json`.

## 5. Ghi chú tại thời điểm đóng gói

- 4 service đều `active`: `agv`, `agv-cam`, `agv-cam-range`, `agv-gateway`
- LiDAR 10 Hz, camera hoạt động, 2 model nạp thành công
- **ESP32 không gửi telemetry** (đọc thô `/dev/ttyUSB0` không có byte nào) → chưa có `odom→base_footprint`, SLAM chưa dựng bản đồ. Đây là vấn đề nguồn/cáp phần cứng, không phải mã nguồn.

## 6. Khôi phục V1

V1 nằm ở thư mục `v1/` của repo này:

```bash
tar xzf v1/AGV-V1-20261117.tar.gz
sha256sum -c v1/SHA256SUMS
```

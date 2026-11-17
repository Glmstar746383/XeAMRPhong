# TÓM TẮT DỰ ÁN XE TỰ HÀNH AGV

**Tài liệu bàn giao** · Cập nhật: 17/11/2026

Xe tự hành AGV cỡ nhỏ chạy trong nhà. Nền tảng điều hướng là **LiDAR 2D**, bổ sung **camera** để bù điểm mù vật thấp (dây, cạnh hộp, chân bàn).

---

## Mục lục

1. [Bối cảnh](#1-bối-cảnh)
2. [Phần cứng](#2-phần-cứng)
3. [Truy cập xe](#3-truy-cập-xe)
4. [Dịch vụ trên Pi](#4-dịch-vụ-trên-pi)
5. [Cấu trúc code hiện tại (V2)](#5-cấu-trúc-code-hiện-tại-v2)
6. [Git & GitHub](#6-git--github)
7. [Hiệu chuẩn camera](#7-hiệu-chuẩn-camera)
8. [Quy tắc tránh vật cản](#8-quy-tắc-tránh-vật-cản-kết-hợp-lidar--camera)
9. [An toàn chuyển động](#9-an-toàn-chuyển-động)
10. [Tự hành](#10-tự-hành)
11. [Giao diện Fusion](#11-giao-diện-fusion)
12. [Lỗi đã gặp và cách sửa](#12-lỗi-đã-gặp-và-cách-sửa)
13. [Báo cáo](#13-báo-cáo)
14. [Trạng thái hiện tại & việc còn lại](#14-trạng-thái-hiện-tại--việc-còn-lại)
15. [Lệnh vận hành](#15-lệnh-vận-hành-thường-dùng)
16. [Giới hạn đã biết](#16-giới-hạn-đã-biết)

---

## 1. Bối cảnh

Trong quá trình làm việc đã thực hiện:

- Dọn dẹp thư mục Pi (198 mục → 21, sau đó tinh gọn còn 19 mục code)
- Tách module camera thành thư mục riêng, thêm dịch vụ ROS 2
- Tích hợp camera vào vòng tránh vật cản (cùng LiDAR)
- Làm lại giao diện web, thêm 2 chế độ tự hành
- Vá nhiều lỗi an toàn (watchdog, chống lắc, chống bỏ sót vật cản)
- Đóng gói V1, dọn thành V2, đưa toàn bộ lên GitHub

---

## 2. Phần cứng

| Thành phần | Chi tiết |
|---|---|
| Máy tính | Raspberry Pi aarch64, 8 GB RAM, thẻ 58 GB, Ubuntu 24.04 LTS, kernel 6.8.0-106x-raspi |
| LiDAR | RPLiDAR C1, 360°, 10 Hz, `/dev/ttyUSB1` qua CP2102N, 460800 baud, `frame_id=laser`, max 16 m |
| MCU | ESP32, `/dev/ttyUSB0` qua CH340, 115200 baud, driver động cơ **MKE-M18** (I2C) |
| Camera | USB UVC 640×480 MJPG 30 fps, `/dev/video0` |
| Thân xe | 300 × 212 mm, bánh Ø73 mm, khoảng cách 2 bánh 190 mm |
| LiDAR | Cao 230 mm so với sàn, đặt ngay tâm xe (x=0, y=0) |
| Camera | Ở mũi xe, cao 130 mm, chúc xuống **7,8°** |
| Mạng | eth0, Wi-Fi DHCP (**hiện 192.168.1.14**), Tailscale **100.118.177.83** |

> **Quan trọng:** ESP32 lấy nguồn từ **pin động cơ**, Pi cấp nguồn riêng. Khi chỉ bật Pi, ESP32 im lặng → không có odometry → SLAM không dựng bản đồ → `pose = None`, preflight FAIL ở mục TF. **Đây là bình thường**, không phải lỗi.

---

## 3. Truy cập xe

- SSH key: `C:\Users\Phong\.ssh\pi_agv`
- Mật khẩu Pi: `Minhkhang123` · user `khangho`

`~/.ssh/config`:

```
Host xe        # qua dây LAN, IPv6 link-local
    HostName fe80::2ecf:67ff:fe18:fd02%%18
    User khangho
    IdentityFile C:/Users/Phong/.ssh/pi_agv

Host xe-ts     # qua Tailscale
    HostName 100.118.177.83
    User khangho
    IdentityFile C:/Users/Phong/.ssh/pi_agv
```

```powershell
ssh xe-ts
ssh -i $env:USERPROFILE\.ssh\pi_agv khangho@192.168.1.14
```

Nếu IP đổi: quét LAN tìm cổng 22, `Resolve-DnsName khang.local`, hoặc dùng Tailscale.

> Router bật **AP Isolation** → hai máy cùng Wi-Fi không thấy nhau. Dùng dây LAN hoặc Tailscale.

---

## 4. Dịch vụ trên Pi

| Service | Cổng | Vai trò |
|---|---|---|
| `agv.service` | 8080 | LiDAR + SLAM Toolbox + brain + web UI, `WorkingDirectory=/home/khangho/agv` |
| `agv-cam.service` | 8081 | MJPEG server, `~/agv-cam/app` |
| `agv-cam-range.service` | ROS 2 | Node đo khoảng cách, `~/agv-cam/nodes` |
| `agv-gateway.service` | 8090 | Gateway xác thực, `/opt/agv-gateway` |
| `agv-monitor.service` | — | Log nhiệt độ/điện áp/Wi-Fi mỗi 10 s → `~/logs/power_monitor.log` |
| `agv-health.timer` | — | 30 s/lần; restart `agv` nếu LiDAR chết >30 s, restart `agv-cam-range` nếu camera chết >30 s (1 lần/5 phút) |

---

## 5. Cấu trúc code hiện tại (V2)

`~/agv` **7,6 MB · 19 mục** (trước là 120 MB · 73 mục). `~/agv-cam` 1,2 MB.

```
~/agv/
├── agv_unified_brain.py              não + web :8080 (≈3600 dòng)
├── agv_command_session.py            giao thức serial ESP32
├── agv_navigation.py                 GridPlanner, A*, frontier
├── agv_command_journal.py            nhật ký lệnh
├── agv_ai_bridge.py                  cầu nối 2 model ONNX
├── agv_preflight_static_collector.py chẩn đoán, khoá cổng serial
├── agv_speed_profile.py              rpm ↔ m/s
├── cam_avoid.py                      lớp chặn vật cản camera
├── index_fusion.html                 giao diện "/" (2 tab)
├── index_cyberpunk.html              giao diện "/classic"
├── slam_scan_fix.yaml                tham số SLAM dự phòng
├── start_agv_system.sh / stop_agv_system.sh
├── ai_local_planner/                 runtime.py + exported/local_planner.onnx (AI 1)
├── models/                           coverage_model.onnx (AI 2)
├── robot/agv.urdf
├── runtime/                          cam_avoid.json, speed.json
├── tools/                            preflight.py, health_check.sh, power_monitor.sh, cam_avoid_selftest.py
└── logs/

~/agv-cam/
├── app/cam_stream.py                 MJPEG :8081
├── nodes/cam_range_node.py           ROS 2: /cam_range, /cam_obstacle, /cam_bg_diff, /cam_support
├── nodes/cam_calib_server.py         web hiệu chuẩn
└── calib/camera_calib.json, floor_ref.jpg
```

Đã xoá: 43 `.bak`, `__pycache__`, `web_tmp`, 7 script rời/launcher cũ, `ai_local_planner/checkpoints` (98 MB), `environments`, `models/runs`, log lệnh cũ.

**Code không đổi một dòng** — chỉ bỏ file không dùng. `~/archive` (29 MB) giữ nguyên.

---

## 6. Git & GitHub

**Repo local trên Pi:** `~/agv`, `~/agv-cam` (không remote). Commit gần nhất: `f60e13c`, `1d61cf3` (cleanup 17/11).

**GitHub:** https://github.com/Glmstar746383/XeAMRPhong

| Commit | Nội dung |
|---|---|
| `3b9f562` | Snapshot toàn bộ Pi vào `pi_home/` (1399 file, 168 MB) |
| `a1a9262` | `v1/AGV-V1-20261117.tar.gz` (71 MB) + README + SHA256SUMS |
| `97a4b95` | `v2/` — mã nguồn sạch dạng file thường |
| `49ead4a` | Bổ sung model ONNX + runtime config còn thiếu |

Tài khoản GCM: **Glmstar746383** (tài khoản cũ `priv1tehub` không có quyền).

---

## 7. Hiệu chuẩn camera

`~/agv-cam/calib/camera_calib.json`:

```
A  = 54.8849        (pixel·m)
v0 = 177.811        (pixel)
cx = 320.17         (pixel)
fx = A / H = 457.4  (với H = 0,12 m)
rms = 0,0156 m (1,56 cm) — 9 mẫu
dải hợp lệ: 0,20 – 1,00 m
```

```
d = A / (v - v0)          khoảng cách tới điểm tiếp xúc sàn
X = (u - cx) · d / fx     lệch ngang
```

Hai lớp bù:
1. Cân bằng sáng toàn cục (0,75–1,35) trước khi so sánh.
2. `bg_diff` > 20 → bỏ qua camera, **trừ khi** vật rộng ≥ 12 cột và ≤ 0,35 m (vẫn chặn).

---

## 8. Quy tắc tránh vật cản (kết hợp LiDAR + camera)

| Quy tắc | Giá trị |
|---|---|
| Camera chỉ chặn **chiều tiến**; quay tại chỗ vẫn cho phép | — |
| Ngưỡng chặn | d < 0,30 m |
| Ngưỡng nhả (hysteresis) | d > 0,45 m |
| Hành lang thân xe | \|X\| ≤ 0,25 m |
| Mất dữ liệu camera | > 2,0 s → bỏ qua (fail-open) |
| Nền lệch | bg_diff > 20 → bỏ qua, trừ vật to + rất gần |
| Vật cản động ghi vào map | chấm bán kính 0,08 m, TTL 60 s, chỉ khi d ≤ 0,45 m và cách xe ≥ 0,25 m |
| Nền lệch → xoá hết dấu động | tránh "xác ma" trên bản đồ |
| Chọn vật | cụm cột **gần nhất** (≥ 8 cột, ±8 px) |
| Chụp nền nóng | topic `/cam_capture_bg`, < 1 s, không restart |
| Tự chụp nền khi ARM | nếu bg_diff > 20 **và** LiDAR trước trống ≥ 0,9 m |

---

## 9. An toàn chuyển động

| Cơ chế | Ngưỡng / hành vi |
|---|---|
| Watchdog máy tính | 2,5 s không có request → STOP ×3, disarm, reset về IDLE |
| SSE `/api/stream` | Giữ heartbeat khi tab bị ẩn |
| Chống lắc | ≥ 3 lần đảo chiều quay trong 3 s mà không tiến → dừng 2 s; 3 lần/20 s → dừng tự hành |
| Lùi thoát kẹt | phía sau trống > 0,30 m → lùi 0,10 m/s trong 1,2 s, cooldown 2 s |
| Giữ hướng quay | 2 s, chỉ đổi khi bên kia thoáng hơn ≥ 0,25 m |
| Tự tìm hướng vòng | 13 hướng ±90°, loại < 0,32 m, ngân sách 8 s |
| XOÁ MAP | Từ chối khi đang ARM (`DISARM_FIRST`), cooldown 8 s |
| Lệnh chuyển động khi chưa ARM | Trả `NOT_ARMED`, **không gửi xuống MCU** |
| Tốc độ | 40–135 RPM |
| Mất LiDAR | scan age > 0,65 s → từ chối lệnh tiến |
| Mất telemetry MCU | d0 age > 0,25 s → STOP |

---

## 10. Tự hành

| Chế độ | Điều kiện | Hành vi |
|---|---|---|
| `EXPLORE` | map + TF | Frontier, hết thì về Home |
| `COVERAGE` | map + TF | Phủ kín sàn bằng model ONNX 2 |
| `POINT` | map + A* | Đi tới toạ độ |
| `DIRECT` | không cần map | Bám hướng B, vừa đi vừa quét |
| `OPEN` | khi hết frontier | 24 hướng, hướng trống nhất ≥ 1,8 m, tiến 1,2 m |
| `RETURNING_HOME` | xong việc | Về vị trí xuất phát |

- Ngân sách tính frontier: **2,0 s** (trước 0,5 s → hay trả rỗng, xe đứng yên).
- Hết frontier 20 s → kết thúc **một phần**, báo % và về Home.
- Blacklist che hết mục tiêu → xoá blacklist, thử lại một lần.

**Tốc độ:** 40 RPM = 0,153 m/s · 55 RPM = 0,211 m/s · 135 RPM = 0,518 m/s. Quay 40 RPM = 1,597 rad/s.

```bash
curl "http://127.0.0.1:8080/api/auto_config?speed=55&turn=45"
```

---

## 11. Giao diện Fusion

Mở `http://<ip>:8080` (giao diện cũ: `/classic`).

- Radar LiDAR 360°, vòng 1–4 m, nón camera ±25°, dấu × đỏ cho vật cản động, marker B.
- Camera MJPEG trực tiếp + số đo + trạng thái.
- Chip: ARMED / AUTO / MODE / FAULT / LiDAR / CAMERA / AVOID.
- Tab ① Trực tiếp A→B; Tab ② Quét map trước (XOÁ MAP, % phủ, frontier).
- Panel **Tốc độ** (4 slider), panel **Ngưỡng camera** (chặn/nhả/hành lang/timeout + CHỤP LẠI NỀN SÀN + test logic).
- Banner đỏ khi bị chặn/lỗi, nút ARM nhấp nháy khi chưa ARM.
- Bấm vào radar để chọn điểm B.

### API chính

```
/api/telemetry  /api/diagnostics  /api/map_full
/api/cmd?val=ARM|STOP|RESET|RESET_MAP|V v w
/api/auto?act=START&mode=EXPLORE|COVERAGE|POINT|DIRECT&x=&y=
/api/auto?act=STOP
/api/cam  /api/cam_config  /api/cam_capture_bg  /api/cam_gate?v=&d=
/api/auto_config?speed=&turn=
/api/frontier_debug?radius=  /api/open_direction  /api/alive  /api/stream
```

---

## 12. Lỗi đã gặp và cách sửa

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `MKE_M18_INIT_FAILED` | MCU init driver I2C lúc boot | Gửi `RESET` (đôi khi 2 lần) |
| Brain không nhận `/scan`, `/cam_range` | Executor ROS kẹt sau boot nguội | Restart `agv`; đã chuyển **MultiThreadedExecutor** |
| Camera "active" nhưng không publish | Timeout đọc snapshot 3 s làm treo timer | Giảm còn 0,8 s |
| Node camera restart liên tục | `NameError: support` | Đã sửa |
| "Hết frontier" dù còn chỗ | Tính frontier vượt 0,5 s | Tăng 2,0 s |
| Xe quay loạn | Bấm XOÁ MAP khi đang chạy | Chặn khi ARM + cooldown 8 s |
| Báo vật ở xa 1 m | Chọn percentile 20 | Chọn cụm gần nhất |
| Bỏ qua vật to sát mũi | Tắt camera tuyệt đối khi nền lệch | Thêm `support ≥ 12` + d ≤ 0,35 m |
| Dừng nhầm khi chuyển tab | Chrome throttle heartbeat | Thêm SSE |
| `DISARMED_REJECT_S` | Gửi lệnh chạy khi chưa ARM | Chặn tại Pi → `NOT_ARMED` |
| Pi tự reboot 4 lần (14/11) | Mất nguồn (throttled=0x0, temp 39°C) | Cần UBEC riêng cho Pi |
| Push GitHub 403 | Credential `priv1tehub` | Đăng nhập `Glmstar746383` |
| V2 thiếu model ONNX | `.gitignore` của app chặn `exported/` | `git add -f` |

### Lỗi công cụ khi thao tác từ Windows

- PowerShell pipe làm **hỏng UTF-8** → upload bằng `Start-Process plink -RedirectStandardInput <file>`.
- `Get-Content -Raw` mặc định đọc ANSI → chỉ dùng cho script ASCII.
- `plink` cần `-hostkey SHA256:BnfdFF/iXP6Ths9TwomFQ3JJtLVQcgbjuEnuRyBDYPk`.
- Script `.sh` sau khi upload cần `sed -i 's/\r$//'`.
- Quote lồng trong PowerShell hay hỏng → viết script ra file rồi chạy.

---

## 13. Báo cáo

`docs/BAO-CAO-AGV.docx` (945 KB, 5 ảnh). 11 chương: phần cứng, thuật toán, hiệu chuẩn, giao diện, nhật ký công việc, kiểm thử, **chương 11: nhật ký 14/11**.

Bản sao trong repo GitHub ở `report/`.

---

## 14. Trạng thái hiện tại & việc còn lại

**Đang chạy:** 4 service active, LiDAR 10 Hz, camera OK, 2 model nạp thành công.

**Chưa xác nhận:** ESP32 im lặng vì **chưa cấp nguồn động cơ** — không phải lỗi.

Khi bật nguồn động cơ:

```bash
sudo systemctl restart agv
python3 ~/agv/tools/preflight.py     # cần 0 FAIL
```

Việc tiếp theo có thể làm:

1. Xác nhận V2 chạy đúng trên xe
2. **Lưu/nạp bản đồ** (map_saver) — để không phải quét lại mỗi lần
3. **Nút dừng khẩn cấp vật lý** ngắt nguồn motor (an toàn tuyệt đối)
4. Cảm biến depth/ToF cho vật thấp nếu cần triệt để

---

## 15. Lệnh vận hành thường dùng

```bash
# kiểm tra
python3 ~/agv/tools/preflight.py
systemctl is-active agv agv-cam agv-cam-range agv-gateway

# log
tail -30 ~/agv/runtime/brain.log
tail -20 ~/agv-cam/logs/cam_range.log
tail -20 ~/logs/power_monitor.log

# chẩn đoán tự hành
curl -s "http://127.0.0.1:8080/api/frontier_debug"
curl -s "http://127.0.0.1:8080/api/open_direction"

# khởi động lại
sudo systemctl restart agv
sudo systemctl restart agv-cam-range
```

---

## 16. Giới hạn đã biết

1. Bản đồ **không lưu ra đĩa** — restart `agv` là mất.
2. Camera phụ thuộc ảnh nền; vật đứng yên lúc chụp nền sẽ thành "nền".
3. Vật sát < ~15 cm có thể ra khỏi khung hình.
4. LiDAR 2D mù dưới mặt phẳng quét 23 cm (lý do cần camera).
5. `DIRECT` không dùng bản đồ để chọn đường vòng thông minh.
6. Không tự ARM khi boot (cố ý).
7. Pi cần nguồn riêng ổn định — từng tự reboot nhiều lần.

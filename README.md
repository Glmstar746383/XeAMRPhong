# Xe AMR Phong — AGV tự hành (LiDAR + Camera)

Kho lưu trữ toàn bộ mã nguồn, dữ liệu và tài liệu của xe tự hành AGV.

## Nội dung

| Thư mục | Nội dung |
|---|---|
| `pi_home/agv/` | Ứng dụng chính: brain, web server, ROS node, thuật toán, giao diện |
| `pi_home/agv-cam/` | Module camera: MJPEG server, node đo khoảng cách, công cụ hiệu chuẩn |
| `pi_home/archive/` | Bản sao lưu các phiên bản cũ và script một lần |
| `pi_home/firmware/` | Binary ESP32 và các bản firmware cũ |
| `pi_home/docs/` | Tài liệu vận hành, cấu trúc, hướng dẫn |
| `pi_home/docs/backups/` | Git bundle của hai repo gốc (`agv`, `agv-cam`) |
| `pi_home/rplidar_c1_ws/` | ROS 2 workspace cho RPLiDAR C1 |
| `pi_home/slam_calibration_tools/` | Tham số SLAM đã tinh chỉnh |
| `pi_home/logs/` | Log giám sát nguồn và log cũ |
| `report/BAO-CAO-AGV.docx` | Báo cáo kỹ thuật đầy đủ (Word) |

## Phần cứng

- Raspberry Pi (aarch64, 8 GB RAM), Ubuntu 24.04 LTS
- RPLiDAR C1 — 2D, 360°, 10 Hz, USB-UART CP2102N
- ESP32 — điều khiển động cơ qua driver MKE-M18 (I2C), USB-UART CH340
- Camera USB UVC 640×480, MJPEG 30 fps
- Thân xe 300 × 212 mm, bánh Ø73 mm, khoảng cách 2 bánh 190 mm
- LiDAR cao 230 mm, camera ở mũi cao 130 mm, chúc xuống 7,8°

## Dịch vụ trên Pi

| Service | Cổng | Vai trò |
|---|---|---|
| `agv.service` | 8080 | LiDAR + SLAM + brain + web UI |
| `agv-cam.service` | 8081 | Luồng MJPEG |
| `agv-cam-range.service` | ROS 2 | Node đo khoảng cách từ camera |
| `agv-gateway.service` | 8090 | Gateway xác thực |
| `agv-monitor.service` | — | Giám sát nguồn, nhiệt độ, Wi-Fi |
| `agv-health.timer` | — | Tự restart khi cảm biến ngừng dữ liệu |

## Chạy nhanh

```bash
ssh khangho@<ip-pi>
python3 ~/agv/tools/preflight.py     # kiểm tra tổng thể
sudo systemctl restart agv           # khởi động lại toàn bộ
```

Mở giao diện: `http://<ip-pi>:8080`
Camera: `http://<ip-pi>:8081/view`

## Tài liệu

- `pi_home/docs/CAU-TRUC.md` — cấu trúc thư mục và dịch vụ
- `pi_home/docs/QUY-TRINH-CHAY-XE.md` — quy trình chạy xe
- `pi_home/docs/CAMERA-AVOID.md` — cơ chế tránh vật cản bằng camera
- `pi_home/docs/HAI-CHE-DO.md` — hai chế độ tự hành A→B

## Khôi phục lịch sử git

```bash
git clone pi_home/docs/backups/agv.bundle agv
git clone pi_home/docs/backups/agv-cam.bundle agv-cam
```

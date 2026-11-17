# QUY TRÌNH CHẠY XE AGV — TEST ĐẦY ĐỦ TÍNH NĂNG

Cập nhật: 2026-11-13

---

## 0. Mỗi lần bật xe

1. Bật công tắc nguồn xe (Pi + driver động cơ).
2. Đợi ~60 giây cho Pi boot và 4 service lên.
3. Từ laptop:

```powershell
ssh khangho@khang.local
```

4. Chạy preflight (chỉ đọc trạng thái, không điều khiển):

```bash
python3 ~/agv/tools/preflight.py
```

Chỉ chuyển sang bước tiếp khi kết quả không có `FAIL`.

---

## 1. Mở giao diện điều khiển

| Cách | Địa chỉ | Khi nào dùng |
|---|---|---|
| Trực tiếp | `http://192.168.1.4:8080` | trong LAN, nhanh |
| Qua gateway | `http://192.168.1.4:8090` | cần đăng nhập, có log CSV |

Tài khoản gateway: xem `~/docs/private/agv_gateway_credentials.txt` trên Pi.

Giao diện có: nút **ARM**, **W/A/S/D/Q/E** (lái tay), **Auto Explore**,
**Auto Coverage**, **Nav Goal**, **Reset Map**, **Reset Fault**, tab Radar / SLAM.

---

## 2. Xử lý FAULT trước khi chạy

Nếu preflight báo `fault` hoặc `latched`:

```bash
curl -s "http://127.0.0.1:8080/api/cmd?val=RESET"
sleep 3
curl -s "http://127.0.0.1:8080/api/telemetry" | python3 -c "import sys,json;c=json.load(sys.stdin)['control'];print(c['fault'],c['latched'],c['latest_d0']['safety'])"
```

Kết quả đúng: `None True DISARMED`.

> **Lưu ý:** đôi khi RESET lần đầu chưa clear (ACK của MCU về sát thời điểm ghi lệnh).
> Cứ gửi lại lần 2. Nếu vẫn còn fault thì đó là lỗi phần cứng thật (xem mục 7).

---

## 3. Test tại chỗ — KÊ BÁNH XE LÊN KHI CHẠY BƯỚC NÀY

1. Bấm **ARM** (hoặc `curl "http://127.0.0.1:8080/api/cmd?val=ARM"`).
   Kiểm tra telemetry: `armed: true`.
2. Nhấp **W** thật ngắn (0.2 s) rồi **STOP**.
3. Xem `l_rpm` / `r_rpm` trong telemetry có lên đúng chiều không.
4. Thử **A** / **D** (quay trái/phải), xác nhận chiều quay đúng.
5. **S** lùi, kiểm tra chiều.
6. Bấm **STOP** và xác nhận `safety` về `DISARMED`, các rpm về 0.

Nếu bánh quay ngược chiều mong muốn → dừng lại, báo tôi để sửa dấu trong
`agv_speed_profile.py` / lệnh `V`.

---

## 4. Test trên sàn — dựng map

1. Đặt xe ở vị trí xuất phát, không chạm vật cản trong 30 cm.
2. Mở tab **SLAM** trên UI, xác nhận có tia laser và map bắt đầu vẽ.
3. Bấm **Auto Explore**. Xe tự chạy quét mở rộng map.
4. Quan sát:
   - tab Radar: tia và vùng vật cản
   - `explore_phase` trong telemetry
   - nếu xe đứng im > 5 s → STOP, chạy `/api/diagnostics` xem `blockers`

Dừng: bấm **STOP** hoặc `curl "http://127.0.0.1:8080/api/auto?act=STOP"`.

> Bản đồ **không được lưu ra đĩa**. Mỗi lần restart `agv.service` là mất map.
> Muốn lưu map lâu dài thì cần thêm bước `ros2 run nav2_map_server map_saver_cli`
> — nói tôi làm nếu cần.

---

## 5. Test các chế độ tự hành

| Chức năng | Lệnh API | Ghi chú |
|---|---|---|
| Quét mở rộng map | `/api/auto?act=START&mode=EXPLORE` | cần TF + map |
| Phủ kín sàn | `/api/auto?act=START&mode=COVERAGE` | dùng model `coverage_model.onnx` |
| Đi tới toạ độ | `/api/auto?act=START&mode=POINT&x=1.2&y=0.5` | toạ độ trong `map` frame |
| Dừng khẩn | `/api/auto?act=STOP` | luôn dùng được |

Nếu trả về `422 FAILED`, đọc trường `blockers`:

| Blocker | Nghĩa | Cách xử lý |
|---|---|---|
| `NOT_ARMED` | chưa ARM | bấm ARM |
| `LATCHED` | cần ARM lại sau reset | ARM |
| `FAULT` | MCU hoặc phần mềm báo lỗi | RESET |
| `D0_STALE` | MCU không trả telemetry | kiểm tra cáp USB / nguồn |
| `SCAN_STALE` | LiDAR không phát | `systemctl restart agv` |
| `MAP_NOT_READY` | chưa có map | chạy EXPLORE trước |
| `TF_NOT_READY` | SLAM chưa publish map→odom | chờ 2–3 s, hoặc Reset Map |
| `SCAN_MOUNT_TF_NOT_READY` | thiếu TF gắn LiDAR | kiểm tra static transform |

---

## 6. Camera: vật nhỏ thì DỪNG CHỜ, vật to thì NÉ (V2.1)

Camera đã tham gia tránh vật cản theo luật riêng:

| Tình huống | Xe làm gì |
|---|---|
| Vật **nhỏ** (rộng < 0,15 m: dây, chân bàn, đồ chơi) | **Dừng hẳn**, giữ nhiệm vụ, chờ lấy vật ra rồi **tự chạy tiếp** |
| Vật **to** (≥ 0,15 m: thùng, ghế, balo) | Chặn chiều tiến + quay né như vật cản LiDAR; 5 lần bị chặn → đổi mục tiêu |
| Sàn trống | Chạy bình thường |

UI Fusion hiện chip `CHỜ VẬT CẢN` / `ĐANG CHỜ`; phase ghi rõ khoảng cách và số giây đã chờ.
Chi tiết + cách tinh chỉnh: `docs/CAMERA-CHO-NE.md`.

```bash
# ảnh tĩnh
curl -s -o /tmp/s.jpg http://127.0.0.1:8081/snapshot.jpg && ls -l /tmp/s.jpg

# stream xem trên điện thoại/trình duyệt
#   http://192.168.1.14:8081/view

# khoảng cách camera đo được + trạng thái chờ
curl -s http://127.0.0.1:8080/api/cam
```

Kỳ vọng:

- Sàn trống trong dải 0,20–1,00 m → `cam.d = 9.9`, chip `SẴN SÀNG`
- Đưa hộp/dây vào cách 0,3–0,5 m → `d` giảm, `class` = `small`/`large`, `waiting` = true nếu nhỏ
- `bg_ok = false` (nền lệch) → bấm **CHỤP LẠI NỀN SÀN** hoặc ARM để xe tự chụp (LiDAR trước trống ≥ 0,9 m)

---

## 7. Khi có sự cố

```bash
systemctl status agv agv-cam agv-cam-range --no-pager
tail -30 ~/agv/runtime/brain.log
tail -20 ~/agv-cam/logs/cam_range.log
journalctl -u agv -n 50 --no-pager
```

| Hiện tượng | Nguyên nhân thường gặp |
|---|---|
| `MKE_M18_INIT_FAILED` | MCU không init được driver I2C lúc boot → tắt/bật lại nguồn động cơ, rồi RESET |
| `D0_STALE` | mất cáp USB ESP32, hoặc MCU treo → rút cắm lại |
| `SCAN_STALE` | LiDAR mất nguồn/cổng → `sudo systemctl restart agv` |
| Xe không nhận ARM | còn `LATCHED`/`FAULT` → RESET rồi ARM lại |

Khởi động lại toàn bộ:

```bash
sudo systemctl restart agv
```

---

## 8. An toàn

- Luôn có tay trên **STOP** khi test lần đầu.
- Kê bánh khi test động cơ.
- Đặt tốc độ thấp (`AGV_AUTO_SPEED_RPM=40`) cho tới khi tin hệ thống.
- Không test gần cầu thang / mép bàn.
- Nếu xe tự chạy bất thường: rút nguồn động cơ, không cố bấm STOP nhiều lần.

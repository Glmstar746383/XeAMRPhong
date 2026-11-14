# CAMERA + LIDAR — TRÁNH VẬT CẢN KẾT HỢP

Cập nhật: 2026-11-13

## Vì sao cần camera

LiDAR C1 là LiDAR 2D: nó chỉ quét **một mặt phẳng** ở độ cao của nó. Mọi thứ
thấp hơn mặt phẳng đó đều vô hình với LiDAR:

- dây điện, dây xạc trên sàn
- cạnh dưới của hộp/thùng
- chân bàn, mép thảm, bậc thấp
- chân người

Camera đã hiệu chuẩn (`pinhole_ground`) đo được khoảng cách tới điểm tiếp xúc
của vật với sàn, nên lấp đúng điểm mù đó.

## Luồng dữ liệu

```
camera /dev/video0
   └─> cam_stream.py                (:8081, MJPEG)  ──> giao diện
         └─> cam_range_node.py      (ROS 2, 10 Hz)
               ├─> /cam_range       Float32  (m), 9.9 = trống
               └─> /cam_obstacle    PointStamped x = lệch ngang, y = khoảng cách
                     └─> agv_unified_brain.py
                           └─> cam_avoid.py
                                 └─> chan tai send_cmd()   (V/M)  +  telemetry/UI
```

## Nguyên tắc an toàn

| Quy tắc | Giá trị mặc định |
|---|---|
| Chỉ chặn chiều **tiến** (`v > 0`) | lùi/quay không bị ảnh hưởng |
| Ngưỡng chặn | `d < 0.30 m` |
| Ngưỡng nhả (hysteresis) | `d > 0.45 m` |
| Hành lang thân xe | `abs(x) <= 0.25 m` |
| Mất tín hiệu | quá `2.0 s` → **bỏ qua camera**, chạy bằng LiDAR |
| LiDAR | vẫn là nguồn chính, camera chỉ là lớp phụ |

Khi bị chặn, brain gửi `V 0.000 0.000` thay vì lệnh tiến, ghi event `cam_block`,
và (ở chế độ tự hành) sau 5 lần liên tiếp sẽ loại mục tiêu đó để tìm hướng khác.

## Cấu hình

Ưu tiên 1 — trên giao diện: panel **Ngưỡng camera** → kéo slider → **Áp dụng**.

Ưu tiên 2 — API:

```bash
curl -s "http://127.0.0.1:8080/api/cam"
curl -s "http://127.0.0.1:8080/api/cam_config?enabled=1&stop_m=0.30&clear_m=0.45&half_w=0.25&timeout_s=2.0"
```

Ưu tiên 3 — biến môi trường trong `/etc/systemd/system/agv.service`:

```
AGV_CAM_AVOID=1        # 0 = tắt hoàn toàn
AGV_CAM_STOP_M=0.30
AGV_CAM_CLEAR_M=0.45
AGV_CAM_HALF_W=0.25
AGV_CAM_TIMEOUT_S=2.0
```

Cấu hình chỉnh qua API/UI được lưu ở `~/agv/runtime/cam_avoid.json` và giữ
nguyên sau khi restart.

## Giao diện

| Đường dẫn | Nội dung |
|---|---|
| `/` hoặc `/ui` | **AGV Fusion** — radar LiDAR + camera trực tiếp + điều khiển |
| `/classic` | Giao diện Cyberpunk cũ (giữ nguyên, dùng khi cần) |
| `:8081/view` | Camera toàn màn hình (mở trên điện thoại) |
| `:8081/stream` | Luồng MJPEG thô (dùng cho thẻ `<img>`) |

Giao diện Fusion gồm:

- **Radar LiDAR**: 360 tia, vòng khoảng cách 1–4 m, nón camera ±25°, thân xe
- **Camera live** kèm số đo và trạng thái chặn
- **Chips trạng thái**: ARMED / AUTO / MODE / FAULT / LiDAR / CAMERA / AVOID
- **Điều khiển**: ARM, RESET, EXPLORE, COVERAGE, DỪNG AUTO, D-pad, DỪNG KHẨN CẤP
- **Panel ngưỡng camera** + nút **Thử** kiểm tra logic không cần cho xe chạy

## API

| Endpoint | Chức năng |
|---|---|
| `GET /api/cam` | trạng thái camera avoid + cấu hình hiện tại |
| `GET /api/cam_config?...` | đổi ngưỡng, lưu ra file |
| `GET /api/cam_gate?v=0.12&d=0.20&x=0` | **test logic**: có chặn hay không, không cần phần cứng |
| `GET /api/telemetry` | có thêm trường `camera` |

Ví dụ kiểm tra:

```bash
curl -s "http://127.0.0.1:8080/api/cam_gate?v=0.12&d=0.20"   # allow=false, CAM_OBSTACLE
curl -s "http://127.0.0.1:8080/api/cam_gate?v=0.12&d=0.60"   # allow=true
curl -s "http://127.0.0.1:8080/api/cam_gate?v=-0.1&d=0.20"   # allow=true (lùi)
```

## Tinh chỉnh thực tế

| Hiện tượng | Cách sửa |
|---|---|
| Báo nhầm bóng đổ / vân sàn | tăng `--thr` của node (mặc định 28) hoặc tăng `stop_m` |
| Bỏ sót vật nhỏ/đen | giảm `--thr`, giảm `--min-col` |
| Chặn khi vật đi ngang qua mép | giảm `half_w` |
| Xe dừng quá xa vật | giảm `stop_m` (0.20–0.25) |
| Dừng rồi vẫn nhích | tăng `clear_m` |

Tham số của node nằm trong `/etc/systemd/system/agv-cam-range.service`
(phần `ExecStart`), sau khi sửa: `sudo systemctl daemon-reload && sudo systemctl restart agv-cam-range`.

## Kiểm chứng ngày 2026-11-13

| Test | Kết quả |
|---|---|
| Selftest logic (11 case) | pass: chặn/nhả/hysteresis/lùi/lệch ngang/mất tín hiệu |
| Giả lập vật 0.15 m qua ROS | lệnh `V 0.10 0` → `CAM_BLOCKED` |
| Vật 0.70 m | lệnh tiến không bị camera chặn |
| Lệch ngang 0.50 m | không chặn |
| Thực tế | LiDAR thấy 0.70 m, camera thấy **0.18 m** (vật thấp) → UI báo CÓ VẬT CẢN |
| `/cam_range` | 10 Hz, ổn định |

## Rollback

```bash
cd ~/agv
git log --oneline            # tìm commit truoc khi them camera
git revert <commit>          # hoac: git checkout <commit> -- agv_unified_brain.py
sudo systemctl restart agv
```

Tắt nhanh không cần revert:

```bash
curl -s "http://127.0.0.1:8080/api/cam_config?enabled=0"
```

---

## Vật cản thấp được ghi vào bản đồ (cập nhật 2026-11-14)

Camera không chỉ chặn tức thời mà còn **đánh dấu ô vật cản vào bản đồ**.

### Cách hoạt động

`
Camera đo d (m) và lệch ngang lat (m) tại điểm tiếp xúc sàn
        │
        ├─ điều kiện: bg_diff < 20, vật ổn định >= 5 khung, d <= 0.6 m
        │
        ▼
Chiếu sang frame map theo pose (x, y, θ):
   Xw = x + d·cosθ + lat·sinθ
   Yw = y + d·sinθ − lat·cosθ
        │
        ▼
Đánh dấu các ô trong bán kính 0,12 m quanh (Xw, Yw) là OCCUPIED
   (lớp vật cản động, tự hết hạn sau 60 giây)
`

Lớp này được chồng lên bản đồ trước khi A* tìm đường, nên:

- A* tự vẽ đường vòng quanh đệm/thùng thay vì lao vào.
- Frontier nằm sau vật cản bị loại vì không có đường tới.
- Xe không lặp lại việc đâm vào chỗ đã biết có vật.

### Chốt an toàn

| Chốt | Giá trị | Mục đích |
|---|---|---|
| Nền phải khớp | bg_diff ≤ 20 | tránh vẽ ô sai khi xe đổi chỗ |
| Ổn định | ≥ 5 khung (~0,5 s) | tránh nhiễu nhất thời |
| Khoảng cách | ≤ 0,6 m | chỉ ghi vật thật gần |
| Cách thân xe | ≥ 0,25 m | không khoá ô xe đang đứng |
| Thời gian sống | 60 s | vật dời đi thì bản đồ tự sạch |

### Hiển thị

Các điểm vật cản động hiện trên radar dạng **dấu × đỏ**. Telemetry:
map_info.dyn_obstacles = [[x, y], ...].

### Nếu dấu × nằm sai bên

Camera có thể bị hiểu ngược trái/phải tuỳ hướng lắp. Đổi dấu bằng biến môi trường:

`
AGV_CAM_LAT_SIGN=-1
`

trong /etc/systemd/system/agv.service, sau đó daemon-reload và restart.

### Giới hạn

- Chỉ trong dải giữa ảnh (35–65% bề ngang).
- Chỉ tới 0,6 m.
- Không thấy phía sau vật cản.
- Vật đứng yên trong tầm nhìn sau khi chụp nền sẽ thuộc về nền, không bị ghi.

---

## Tự động thích nghi vị trí và ánh sáng (cập nhật 2026-11-14)

Mỗi lần chạy ở chỗ khác nhau, nền sàn và ánh sáng đều khác. Hệ thống xử lý bằng 2 lớp:

### Lớp 1 — Cân bằng sáng tự động

Trước khi so sánh với ảnh nền, node chuẩn hoá độ sáng trung bình của khung hình
theo ảnh nền (hệ số 0,75–1,35). Nhờ vậy chênh lệch sáng ngày/đêm hoặc auto-exposure
không còn làm hỏng phép so sánh.

Ví dụ đo được: diff thô 42,85 → sau cân bằng 17,86.

### Lớp 2 — Tự chụp lại nền khi ARM

Khi bấm ARM, brain kiểm tra:

`
nếu bg_diff > 20 (nền lệch) VÀ LiDAR phía trước trống >= 0,90 m
    → phát topic /cam_capture_bg
    → node chụp ngay khung hình hiện tại làm nền mới (không restart)
`

Nếu phía trước còn vật gần hơn 0,90 m, hệ thống **không** tự chụp (tránh lấy vật làm nền)
và ghi cảnh báo vào log.

### Chụp nóng (không restart)

Trước đây chụp nền phải restart node (3–5 giây). Nay node nhận topic
/cam_capture_bg và chụp ngay trong bộ nhớ, đồng thời ghi đè loor_ref.jpg.

Đo thực tế: gọi API → sau 1 giây g_diff từ 16,9 xuống 1,2.

### Quy trình khi đổi chỗ chạy

1. Đặt xe ở vị trí mới, trước mặt trống >= 1 m
2. Bấm ARM
3. Hệ thống tự chụp nền nếu cần; chip chuyển CAMERA OK
4. Nếu chip vẫn báo CAMERA LỆCH NỀN: dọn vật trước mặt rồi bấm CHỤP LẠI NỀN SÀN

Lưu ý: vật nằm trong 1 m trước mặt lúc ARM sẽ bị coi là nền. Luôn dọn trước khi ARM.

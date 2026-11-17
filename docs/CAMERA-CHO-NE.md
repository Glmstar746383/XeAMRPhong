# CAMERA V2.1 — VẬT NHỎ THÌ DỪNG CHỜ, VẬT TO THÌ NÉ

Cập nhật: 2026-11-17 · Áp dụng trên Pi (`~/agv`, `~/agv-cam`)

---

## 1. Vì sao đổi

Bản cũ: camera thấy vật là **chặn + quay tìm hướng vòng** (giống LiDAR). Nhưng:

- Vật nhỏ (dây, chân bàn, đồ chơi) **không nên vòng** — vòng qua là đè lên hoặc bỏ sót.
- Bộ phát hiện cũ chọn theo **từng cột**, nhận cả cụm 10 cột (~6 mm) sát mép ROI và
  vạch gạch trên sàn bóng → báo vật 0,28 m khi sàn trống (đo được: 8/8 khung, support = 10).
- Nền (background) cũ lệch nhưng chỉ số `bg_diff` trung bình 19,8 < ngưỡng 20 nên vẫn "OK",
  trong khi 100 % cột ROI có pixel khác nền > 28.

Bản V2.1: giữ nguyên logic LiDAR/tự hành cũ, **chỉ đổi luật camera**:

| Vật | Hành vi |
|---|---|
| **NHỎ** (< 0,15 m) | **Dừng hẳn** `V 0 0`, giữ nguyên nhiệm vụ (không mất map, không đổi mục tiêu), chờ lấy đi → **tự chạy tiếp** |
| **TO** (≥ 0,15 m) | Chặn chiều tiến, quay tại chỗ né; ghi vật cản động vào map; 5 lần liên tiếp → đổi mục tiêu (như logic cũ) |

---

## 2. Phân loại và ngưỡng

```
rộng_vật (m) = số_pixel_rộng × d / fx        fx = A / h_cam = 457,4 px
NHỎ  nếu rộng < small_max_m (mặc định 0,15 m)
```

| Thông số | Mặc định | Ý nghĩa |
|---|---|---|
| `stop_m` | 0,30 m | bắt đầu dừng/chặn |
| `clear_m` | 0,45 m | nhả (hysteresis) — vật nhỏ phải ra xa > 0,45 m |
| `half_w` | 0,25 m | hành lang thân xe ±0,25 m |
| `small_max_m` | 0,15 m | ranh giới nhỏ/to |
| `timeout_s` | 2,0 s | mất dữ liệu camera → fail-open (trừ khi đang chờ) |
| `bg_frac_max` | 0,20 | > 20 % pixel lệch nền trong 0,20–0,60 m → coi là nền lệch |
| vùng phát hiện | 0,25–0,80 m | bỏ vùng sát mũi (chân xe, bóng, lóa sàn) và vùng xa (dễ nhiễu) |
| cụm chạm đáy dải | bị loại | vật sát < 0,25 m hoặc bóng/lóa ở đáy ảnh → không phải vật cản thật |
| kích thước tối thiểu | ≥ 20 mm rộng, ≥ 10 px cao, ≥ 200 px diện tích | lọc vệt sàn, vạch gạch, đốm nhỏ |
| ROI | **hình thang** theo `half_w` | ở 0,3 m phủ ±0,25 m thay vì ±0,06 m như ROI chữ nhật cũ |

Đổi trực tiếp, không cần restart:

```bash
curl "http://127.0.0.1:8080/api/cam_config?small_max_m=0.15&stop_m=0.30&clear_m=0.45&half_w=0.25"
curl "http://127.0.0.1:8080/api/cam"            # xem trạng thái + phân loại
curl "http://127.0.0.1:8080/api/cam_gate?v=0.12&d=0.28&x=0&support=300"   # thử logic
```

Hoặc trên giao diện Fusion, panel **Ngưỡng camera** có thêm slider
**"Vật nhỏ < (m)"** (V2.2) — kéo rồi bấm **Áp dụng**.

`support` = bề rộng cụm (pixel): 10 px ≈ 6 mm → NHỎ; 300 px ≈ 0,18 m → TO (tại d = 0,28 m).

---

## 3. Bộ phát hiện mới (cam_range_node.py)

1. **Cụm 2D (connected components)** thay vì "cột thấp nhất":
   - morphology open 3×3 (diệt vạch gạch 1–2 px) → close 5×5 (nối vật bị đứt)
   - bỏ cụm **chạm mép trái/phải ROI**
   - yêu cầu **rộng ≥ 20 mm, cao ≥ 10 px, diện tích ≥ 200 px**
2. **Kiểm tra màu**: cụm chỉ được coi là vật thật nếu
   `ΔV ≥ 25` hoặc `ΔS ≥ 20` hoặc chênh sáng rất mạnh (`Δgray ≥ 55`).
   Phản chiếu trên sàn bóng giữ nguyên màu/độ bão hoà → bị loại.
3. **Chỉ số nền mới**, chỉ đo trong dải an toàn **0,20–0,60 m**:
   - `/cam_bg_diff` = chênh sáng trung bình
   - `/cam_bg_frac` = **tỉ lệ pixel** khác nền (0..1) → dùng để phát hiện nền lệch
     (đồ đạc/người đi lại phía xa không còn làm sai chỉ số)
4. Chọn **cụm gần nhất** trong các cụm hợp lệ (an toàn nhất), điểm tiếp xúc = đáy cụm.

Kết quả đo trên chính khung hình đã báo sai:

| | Trước | Sau |
|---|---|---|
| Khung báo vật 0,28 m | 8/8 | **0/8** |
| Vật thật 2 cm ở 0,3 m | — | vẫn bắt (≈ 33 px rộng) |

### 3b. ROI hình thang (V2.2)

ROI cũ là hình chữ nhật 35–65 % chiều ngang: ở 0,28 m chỉ nhìn ±**0,06 m**, trong khi
thân xe ±0,15 m → vật lệch bên không thấy. V2.2 đổi sang **hình thang**:

```
mỗi hàng v: d = A / (v - v0) ; nửa bề rộng ảnh = half_w · fx / d
```

- Ở 0,30 m: phủ ±0,25 m; ở 0,60 m: ±0,25 m; luôn đúng hành lang thân xe.
- Cụm phải có **tâm nằm trong ±half_w**; cụm chạm mép ảnh bị bỏ.
- Giới hạn vật lý: ở 0,25 m FOV chỉ tới ±0,17 m (không thể thấy rộng hơn).

Test chèn vật 3 cm (ảnh thật, nền vừa chụp lại):

| Đặt vật | ROI chữ nhật cũ | ROI hình thang |
|---|---|---|
| x = −0,12 m, d = 0,25 m | bỏ sót | **nhận đúng** (31 mm) |
| x = 0, d = 0,30 m | nhận | **nhận đúng** |
| x = +0,15 m, d = 0,45 m | nhận | **nhận đúng** |
| x = −0,18 m, d = 0,55 m | bỏ sót (ngoài 35–65 %) | **nhận đúng** |

Tham số CLI mới của node: `--half-w` (0,25), `--min-range` (0,25), `--max-range` (0,80),
`--min-obj-m` (0,020), `--min-area` (200), `--min-h` (10).

### 3c. Hình thang hiển thị trên ảnh camera

UI Fusion vẽ **đúng hình thang đang dùng để phát hiện** lên ảnh MJPEG (canvas trong
suốt phủ lên ảnh), nên nhìn là biết vật nào gần/xa:

| Dải | Khoảng cách | Màu | Ý nghĩa |
|---|---|---|---|
| 1 | 0,25–0,30 m | đỏ | vùng dừng (stop_m) |
| 2 | 0,30–0,45 m | cam | cảnh báo, đang chờ nhả |
| 3 | 0,45–0,60 m | vàng | theo dõi |
| 4 | 0,60–0,80 m | xanh | xa, chưa can thiệp |

- Vạch trắng mỗi **5 cm**, nhãn `0.30m / 0.45m / 0.60m / 0.80m` ở mép phải.
- Vật đang thấy: dấu ✛ tại (x, d) + nhãn `0.48 m · TO` (đổi màu theo dải).
- Toạ độ vẽ lấy từ hiệu chuẩn: `u = cx + x·fx/d`, `v = v0 + A/d` (A = 54,8849;
  v0 = 177,811; cx = 320,17; fx = 457,4). Nếu hiệu chuẩn lại, cập nhật `CAM_CAL`
  trong `index_fusion.html`.

### 3d. Chống báo sai ở đáy ảnh (V2.3)

Triệu chứng: UI báo `CAM: 0,22 m · CHỜ LẤY VẬT` dù sàn trống. Nguyên nhân: 0,22 m là
**hàng cuối của dải phát hiện** — cụm bị cắt ngang bởi biên dưới, thực chất là bóng
thân xe / lóa sàn bóng ở sát mũi, không phải vật.

Cách sửa: **loại mọi cụm chạm 3 hàng cuối** của dải phát hiện, và nâng `min-range`
lên 0,25 m. Vật thật ở 0,25–0,30 m vẫn có đáy nằm phía trên biên này.

---

## 4. Luồng hoạt động trong brain

```
auto_nav_loop (10 Hz)
  └─ camera.wait_state()  ──► đang CHỜ vật nhỏ?
        ├─ có  → _cam_wait_step(): ghi phase, gửi V 0 0 (giữ session + watchdog), RETURN
        └─ không → chạy logic tự hành cũ (frontier / A* / DIRECT / coverage …)

send_cmd('V v w')
  ├─ CAM_WAIT     → drive V 0 0, trả (True, 'CAM_WAIT')   # không đổi mục tiêu
  ├─ CAM_OBSTACLE → drive V 0 w_away, trả (True, 'CAM_BLOCKED')  # né như LiDAR
  └─ cho phép     → drive bình thường
```

- Dừng bằng `V 0 0` chứ **không dùng STOP** → không disarm, không mất nhiệm vụ, không mất map.
- Đang chờ mà **mất dữ liệu camera** → vẫn dừng (an toàn), UI báo "mất dữ liệu camera".
- Vật nhỏ **không ghi vào map** (tránh "xác ma" sau khi lấy đi).
- Nền lệch → camera fail-open; khi ARM, brain **tự chụp lại nền** nếu LiDAR trước trống ≥ 0,9 m.

---

## 5. Kiểm thử đã chạy trên xe (17/11)

Dùng `/tmp/fake_cam.py` phát giả `/cam_range` + `/cam_obstacle` (ngắt `agv-cam-range` trong lúc test):

| Test | Kết quả |
|---|---|
| Vật nhỏ 0,28 m, rộng 10 px, lệnh `V 0.12 0` | `CAM_WAIT`, bánh 0 rpm, pose không đổi, phase "CHỜ VẬT CẢN NHỎ 0,28 m" |
| Tự hành `DIRECT` + vật nhỏ | phase CHỜ suốt 6 s, pose (0,000; 0,000), bánh 0 |
| Bỏ vật (phát 9,9) | `waiting=False`, hết chờ, vòng tự hành chạy tiếp |
| Mất dữ liệu camera khi đang chờ | vẫn dừng, phase "mất dữ liệu camera — giữ xe dừng an toàn" |
| Vật to 300 px (0,18 m) | `CAM_OBSTACLE` (né), không phải chờ |
| Xa 0,60 m / lệch ngang 0,40 m / lùi | cho phép |
| Sàn trống (detector mới) | `d = 9.9`, `bg_ok = true` |

V2.2 — sau khi **chụp lại nền đúng chỗ**: 10/10 khung báo trống; chèn vật 3 cm ở
4 vị trí (kể cả lệch −0,18 m) đều nhận đúng khoảng cách ±0,01 m và lệch ngang ±0,01 m;
`bg_diff = 1,1`, `bg_frac = 0,0`.

> **Quan trọng:** nếu nền lệch (chụp ở chỗ khác/ánh sáng khác), camera sẽ báo vật giả
> hoặc tự tắt (fail-open). Luôn bấm **CHỤP LẠI NỀN SÀN** khi đổi vị trí, và kiểm tra
> `bg_diff < 10`, `bg_frac ≈ 0`, `d = 9.9` trước khi chạy.

Preflight sau khi sửa: **0 FAIL / 2 WARN**.

---

## 6. Lưu ý vận hành

1. **Luôn chụp lại nền** khi đổi chỗ/đổi ánh sáng: nút *CHỤP LẠI NỀN SÀN* hoặc ARM
   (tự chụp khi LiDAR trước trống). Kiểm tra `bg_ok = true`, `d = 9.9`.
2. Vật nằm ngoài hành lang ±0,25 m hoặc ngoài dải **0,25–0,80 m** sẽ **không** bị phát hiện.
3. Dây/ vật mảnh < ~6 mm ở sát 0,3 m có thể lọt (ngưỡng rộng 10 px). Muốn bắt mảnh hơn:
   `--min-w 8 --min-area 80` (đổi trong service) hoặc thêm cảm biến ToF/depth.
4. Xe dừng chờ **không có timeout** (đúng yêu cầu). Muốn thoát: lấy vật ra, hoặc bấm STOP/DỪNG KHẨN CẤP.
5. Vật TO bị chặn 5 lần → brain đổi mục tiêu; nếu vẫn kẹt, phase ghi "HOLD …" và xe quay tại chỗ.

---

## 7. File đã sửa & rollback

| File | Thay đổi |
|---|---|
| `~/agv-cam/nodes/cam_range_node.py` | detector cụm 2D + màu, chỉ số nền dải an toàn, `/cam_bg_frac` |
| `~/agv/cam_avoid.py` | phân loại nhỏ/to, `CAM_WAIT`, `wait_state()`, snapshot mở rộng |
| `~/agv/agv_unified_brain.py` | subscribe `/cam_bg_frac`; `_cam_wait_step()`; `send_cmd` phân nhánh; auto loop dừng-chờ; tự chụp nền theo `bg_frac` |
| `~/agv/index_fusion.html` | chip `CHỜ VẬT CẢN` / `ĐANG CHỜ`, overlay `CHỜ LẤY VẬT` |

Mọi file đều có bản sao `*.bak_v21_<timestamp>` cùng thư mục:

```bash
cd ~/agv && ls *.bak_v21_*
sudo systemctl restart agv && sudo systemctl restart agv-cam-range
```

Rollback: copy file `.bak_v21_*` mới nhất đè lại rồi restart 2 service trên.

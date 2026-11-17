# LẤY MAP THỦ CÔNG (tự lái) — LƯU & DÙNG LẠI

Cập nhật: 2026-11-17 · Áp dụng cho V2 trên Pi (`~/agv`)

Mục tiêu: bạn tự điều khiển xe đi khắp nhà để SLAM dựng bản đồ, sau đó **lưu bản đồ ra đĩa**
để không phải quét lại (khắc phục giới hạn "restart `agv` là mất map").

---

## 0. Chuẩn bị (1 lần mỗi khi bật xe)

```powershell
ssh khangho@192.168.1.14
python3 ~/agv/tools/preflight.py     # cần 0 FAIL
```

Không có `FAIL` mới đi tiếp. Nếu `fault` khác `None`:

```bash
curl -s "http://127.0.0.1:8080/api/cmd?val=RESET"
sleep 3
curl -s "http://127.0.0.1:8080/api/telemetry" | python3 -c "import sys,json;c=json.load(sys.stdin)['control'];print(c['fault'],c['latched'],c['latest_d0']['safety'])"
```

Kết quả đúng: `None True DISARMED`. (`MKE_M18_INIT_FAILED` lúc mới boot → RESET 1–2 lần.)

---

## 1. Bắt đầu map mới (nên làm, tránh map cũ bị trộn)

- Xe đang **DISARMED**, đứng yên.
- Bấm **XOÁ MAP** trên giao diện (`http://192.168.1.14:8080`, tab ②) hoặc:

```bash
curl -s "http://127.0.0.1:8080/api/cmd?val=RESET_MAP"
```

Lệnh này khởi động lại slam_toolbox, mất ~5–10 s. Chờ đến khi preflight báo
`TF map->base_footprint PASS` và `map` bắt đầu có dữ liệu rồi mới ARM.

> Không bấm XOÁ MAP khi xe đang chạy: brain sẽ trả `DISARM_FIRST` / `AUTO_ACTIVE_STOP_FIRST`.

---

## 2. Lái tay để dựng map

| Cách | Thao tác |
|---|---|
| Giao diện Fusion `/` | Bấm **ARM**, rồi **giữ** nút ▲ ◀ ▶ ▼ (D-pad dưới radar). Thả tay = dừng |
| Giao diện cũ `/classic` | **ARM**, rồi giữ **W A S D** (Q/E chỉnh tốc độ), **Space** = dừng |

Mẹo để map sạch:

- Đi chậm (40–55 RPM), quay đầu xe từ từ; tránh quay quá nhanh làm map nhoè.
- Đi vòng quanh phòng, bám tường cách ~0,4–0,6 m, quay lại vị trí xuất phát để SLAM "khép vòng".
- Đi vào từng phòng/ngóc, đừng để khoảng trống lớn ở giữa.
- Luôn giữ tay trên **STOP**; xe tự dừng nếu mất request quá 2,5 s (watchdog).
- Camera chặn chiều tiến khi vật < 0,30 m trong hành lang ±0,25 m; nếu xe không tiến, lùi ra hoặc quay.

Theo dõi: tab Radar/SLAM trên UI, hoặc

```bash
curl -s "http://127.0.0.1:8080/api/telemetry" | python3 -c "import sys,json;m=json.load(sys.stdin)['map_info'];print(m['w'],'x',m['h'],'| map_ready',m['map_ready'],'| frontier',m['frontiers'])"
```

---

## 3. Lưu map (1 lệnh)

Dừng xe (**STOP** hoặc thả nút), rồi trên Pi:

```bash
bash ~/agv/tools/save_map.sh              # tên tự động map_20261117_161230
bash ~/agv/tools/save_map.sh nha_tang1    # hoặc đặt tên riêng
```

Hoặc từ Windows (không cần ssh vào trước):

```powershell
ssh -i $env:USERPROFILE\.ssh\pi_agv khangho@192.168.1.14 "bash ~/agv/tools/save_map.sh nha_tang1"
```

Kết quả mẫu:

```
ĐÃ LƯU BẢN ĐỒ
  thư mục : /home/khangho/agv/maps
  tên     : nha_tang1
  29K        /home/khangho/agv/maps/nha_tang1.data
  7.7K       /home/khangho/agv/maps/nha_tang1.pgm
  6.8M       /home/khangho/agv/maps/nha_tang1.posegraph
  132        /home/khangho/agv/maps/nha_tang1.yaml
  kích thước: 77 x 102 ô  (3.85 m x 5.10 m)
  độ phân giải: 0.050 m/ô
  gốc toạ độ : [-2.324, -3.674, 0]
```

Tạo ra:

| File | Dùng cho |
|---|---|
| `<ten>.pgm` + `<ten>.yaml` | bản đồ chuẩn ROS (xem ảnh, `nav2_map_server`, in ra giấy) |
| `<ten>.posegraph` (+ `.data`) | đồ thị SLAM, cần cho chế độ localization/nạp lại |
| `latest.pgm/yaml/posegraph` | symlink trỏ về bản mới nhất |

Lưu ý: script tự gửi **STOP** và chờ 2 s trước khi chốt map; nếu muốn bỏ qua
(đang tự hành) thì `SKIP_STOP=1 bash ~/agv/tools/save_map.sh`.

---

## 4. Lấy file về máy Windows (tuỳ chọn)

```powershell
scp -i $env:USERPROFILE\.ssh\pi_agv khangho@192.168.1.14:~/agv/maps/nha_tang1.* .
```

Xem nhanh ảnh map: `.pgm` mở được bằng GIMP/IrfanView, hoặc chuyển PNG:

```bash
python3 -c "from PIL import Image; Image.open('/home/khangho/agv/maps/nha_tang1.pgm').save('/home/khangho/agv/maps/nha_tang1.png')"
```

---

## 5. Dùng lại bản đồ đã lưu

Hiện tại **chưa có chế độ nạp map** trong brain: sau khi restart `agv`, SLAM vẫn quét mới từ đầu.

Đã có sẵn dữ liệu để làm bước tiếp theo (`.posegraph` + `.yaml`):

- Nạp lại bằng SLAM: chạy slam_toolbox ở chế độ `localization` rồi gọi
  `/slam_toolbox/deserialize_map` với `<ten>.posegraph`.
- Hoặc dùng `nav2_map_server` đọc `<ten>.yaml` để hiển thị/nav trên map tĩnh.

Nếu cần, nói tôi thêm: (a) nút **LƯU MAP** trên web UI, (b) script `load_map.sh` +
chế độ localization để mở xe là có map ngay.

---

## 6. Sự cố thường gặp

| Hiện tượng | Nguyên nhân / xử lý |
|---|---|
| `save_map thất bại 3 lần: ... result=255` | slam_toolbox đang bận hoặc map chưa có; STOP, chờ 2 s, chạy lại. Script đã tự thử 3 lần |
| `slam_toolbox không chạy` | `sudo systemctl restart agv`, chờ preflight PASS |
| Map bị "trôi"/lệch sau khi quay nhiều | thiếu khép vòng: cho xe quay lại điểm xuất phát, đi chậm, tránh quay nhanh liên tục |
| Map mất sau khi restart | bình thường — đó là lý do phải lưu bằng script này |
| Xe không nhận ARM sau khi lưu | không liên quan; kiểm tra `fault`/`latched`, gửi RESET |

---

## 7. An toàn

- Kê bánh khi thử động cơ lần đầu; test trên sàn cần người lớn, chỗ trống.
- Không đi gần mép cầu thang/bàn; ưu tiên **DỪNG KHẨN CẤP** trên UI.
- Nếu xe chạy bất thường: ngắt nguồn động cơ (công tắc), đừng cố bấm STOP nhiều lần.
- Pin/nguồn: Pi cần nguồn riêng ổn định; xem `~/logs/power_monitor.log` (`throttled=0x0` là tốt).

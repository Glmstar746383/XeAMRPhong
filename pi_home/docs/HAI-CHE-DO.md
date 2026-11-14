# HAI CHẾ ĐỘ TỰ HÀNH A→B

Cập nhật: 2026-11-13

Cả hai chế độ đều dùng **LiDAR + camera** để tránh vật cản trong lúc di chuyển.
Khác nhau ở chỗ **có quét map trước hay không**.

---

## Chế độ ① — Trực tiếp A→B (không cần map)

Dùng khi: chỗ mới, chưa biết gì về không gian, chỉ cần tới B.

```
Bấm ARM  →  Tab ①  →  nhập X, Y (hoặc bấm vào radar)  →  ĐI TỚI B
```

Xe làm gì:

1. SLAM vừa chạy vừa dựng map từ dữ liệu LiDAR
2. Bám hướng tới B: nếu map đã đủ thì dùng A* (`_follow`), nếu chưa thì dùng
   bộ điều khiển phản xạ `_direct_follow`
3. Gặp vật cản:
   - LiDAR thấy trong ±18° và < 0.30 m → dừng tiến, quay về phía thoáng hơn
   - Camera thấy vật thấp < 0.30 m → chặn tiến (`CAM_BLOCKED`), quay tìm hướng
4. Tới nơi khi cách B ≤ 0.18 m → gửi `V 0 0`, báo `COMPLETED`

Toạ độ: gốc là **vị trí xe lúc bắt đầu**, trục X hướng mũi xe lúc đầu,
trục Y sang trái.

API:

```bash
curl -s "http://127.0.0.1:8080/api/auto?act=START&mode=DIRECT&x=1.5&y=0.0"
curl -s "http://127.0.0.1:8080/api/auto?act=STOP"
```

---

## Chế độ ② — Quét map trước rồi mới đi A→B

Dùng khi: muốn xe đi tối ưu, có bản đồ đầy đủ, rồi mới ra lệnh di chuyển.

```
Bấm ARM  →  Tab ②  →  BẮT ĐẦU QUÉT MAP
          →  xe tự chạy vòng quanh, quét hết, tự về Home, tự STOP
          →  bấm ARM lại
          →  nhập X, Y  →  ĐI TỚI B (theo map)
```

Xe làm gì:

1. **Bước 1**: frontier exploration — tự tìm vùng chưa biết, tự lập đường,
   quét tới khi hết frontier **và** số ô chưa biết < 20
2. Tự tìm đường an toàn về vị trí xuất phát, xác nhận STOP với MCU
3. **Bước 2**: A* trên map đã quét → đường ngắn và ổn định hơn nhiều
4. Trong lúc đi, LiDAR + camera vẫn bật: vật cản **mới xuất hiện** (người đi
   qua, hộp đặt thêm, dây rơi) sẽ bị chặn và xe tự tìm đường vòng hoặc bỏ mục tiêu

API:

```bash
# buoc 1
curl -s "http://127.0.0.1:8080/api/auto?act=START&mode=EXPLORE"
# theo doi: /api/telemetry -> map_info.explore_state, map_ready, unknown_cells, frontiers

# buoc 2 (map_ready = true)
curl -s "http://127.0.0.1:8080/api/auto?act=START&mode=POINT&x=1.5&y=0.0"
```

---

## So sánh

| | ① Trực tiếp | ② Quét trước |
|---|---|---|
| Cần map trước | Không | Có |
| Thời gian tới B | Nhanh hơn lần đầu | Chậm hơn (phải quét) |
| Đường đi | Có thể vòng vèo, đi vào ngõ cụt | Tối ưu theo map |
| Nhiều lần A→B khác nhau | Không hiệu quả | Rất tốt |
| Chỗ hoàn toàn mới | Phù hợp | Vẫn dùng được nhưng quét xong mới đi |
| Tránh vật cản | LiDAR + camera | LiDAR + camera (vật mới) |

---

## Dữ liệu UI cần theo dõi

`GET /api/telemetry` → `map_info`:

| Trường | Ý nghĩa |
|---|---|
| `task_mode` | `IDLE` / `EXPLORE` / `POINT` / `DIRECT` |
| `goal_type` | `FRONTIER` / `COVERAGE` / `HOME` / `POINT` / `DIRECT` |
| `explore_state` | `IDLE` / `EXPLORING` / `RETURNING_HOME` / `COMPLETED` |
| `map_ready` | `true` khi đã quét xong và không còn vùng partial |
| `explore_partial` | `true` nếu hết frontier nhưng còn vùng Unknown |
| `dist_to_goal` | khoảng cách còn lại tới B (m) |
| `phase` | mô tả trạng thái hiện tại |
| `robot_pose` | `[x, y, yaw]` trong frame `map` |

---

## An toàn

- `DIRECT` vẫn phải **ARM** và qua đủ cổng: scan tươi, d0 tươi, body radius hợp lệ
- `DIRECT` **không** bỏ qua chặn camera — lệnh tiến vẫn đi qua `send_cmd`
- Nếu mất LiDAR > `scan_max_age_s` thì dừng, không chạy mù
- Hết đường/không qua được: xe HOLD, không tự lao tiếp
- Muốn dừng bất cứ lúc nào: nút **DỪNG KHẨN CẤP** hoặc `/api/auto?act=STOP`

## Giới hạn hiện tại

- Chế độ ① **không nhìn thấy map** để chọn đường vòng thông minh; nó đi theo
  hướng B + né phản xạ. Gặp ngõ cụt hình chữ U có thể phải lùi ra.
- Chế độ ② phụ thuộc chất lượng map; phòng quá nhiều vật cản mềm (rèm, túi)
  có thể làm frontier không bao giờ hết → xe dừng với trạng thái "xong một phần".
- Map **không lưu ra đĩa**: tắt nguồn/restart `agv.service` là mất map.
  Chế độ ② chỉ có ý nghĩa trong cùng một phiên chạy.

---

## Khi bị chặn — tự tìm hướng vòng (cập nhật 2026-11-13)

Trước đây gặp vật cản là gửi V 0 0 rồi đứng. Nay:

1. **Camera chỉ chặn phần tiến**, vẫn cho quay tại chỗ (_reactive_detour giữ w).
2. **Bộ tìm hướng vòng** _reactive_detour:
   - quét 13 hướng từ -90° đến +90° quanh mũi xe
   - loại hướng có khoảng trống < 0.32 m
   - chọn hướng thoáng nhất, ưu tiên gần hướng tới B
   - quay về hướng đó rồi tiến chậm (0.07–0.10 m/s)
3. Nếu **bị vây kín cả 4 phía**: lùi nhẹ 0.09 m/s nếu phía sau thoáng, không thì quay mạnh 1.0 rad/s.
4. Ngân sách vòng là **8 giây**; quá 8 s vẫn không thoát thì HOLD và báo lý do (an toàn).
5. Áp dụng cho cả chế độ ① và ② (khi A* không tìm được đường).

Trạng thái hiển thị trên UI: "VÒNG VẬT CẢN: +45° (trống 0.80 m)".

Lưu ý: nếu vật cản nằm sát và camera vẫn thấy sau khi quay 90°, xe sẽ tiếp tục
quay tiếp cho tới khi hướng mới thoáng — đây là hành vi mong muốn.

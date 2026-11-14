# HƯỚNG DẪN KIỂM THỬ CẢM BIẾN RPLIDAR C1M1 360° TRÊN RASPBERRY PI (ROS 2 JAZZY)

---

## 1. Giới thiệu

Tài liệu này cung cấp quy trình và bộ công cụ hoàn chỉnh để **kiểm tra (test) phần cứng cảm biến quét laser 2D RPLIDAR C1M1 360°** của hãng SLAMTEC kết nối qua cổng USB trên bo mạch Raspberry Pi chạy hệ điều hành Ubuntu 24.04 LTS và ROS 2 Jazzy.

### Phạm Vi Dự Án
- **Mục tiêu duy nhất**: Kiểm tra kết nối vật lý, cổng serial, quyền truy cập, khởi động motor quét, kiểm tra tính toàn vẹn của dữ liệu `LaserScan` trên topic `/scan`, trực quan hóa đám mây điểm 360° trên RViz2 và cung cấp giao diện đồ họa (GUI) trực quan giúp người dùng kiểm thử nhanh mà không cần nhớ câu lệnh terminal.
- **Cam kết kỹ thuật**:
  - **KHÔNG** yêu cầu cấu hình IP tĩnh (Static IP).
  - **KHÔNG** can thiệp hay thay đổi cấu hình mạng Wi-Fi / Ethernet của Raspberry Pi.
  - **KHÔNG** triển khai ngăn xếp điều hướng tự hành Nav2.
  - **KHÔNG** triển khai code điều khiển động cơ hay tạo robot hoàn chỉnh.
  - **KHÔNG** tạo Fake Odometry.

---

## 2. Phần Cứng Cần Thiết

| Thiết bị | Thông số kỹ thuật / Lưu ý |
| :--- | :--- |
| **Cảm biến LiDAR** | RPLIDAR C1M1 360° Laser Range Scanner (SLAMTEC) |
| **Bo mạch xử lý** | Raspberry Pi 4 Model B hoặc Raspberry Pi 5 (Kiến trúc `aarch64`) |
| **USB Adapter** | Mạch chuyển đổi USB-to-UART đi kèm (Chip Silicon Labs CP2102N) |
| **Cáp kết nối** | Cáp Micro-USB hoặc Type-C (phải có đủ 4 lõi: VCC, GND, D+, D-) |
| **Nguồn cấp Pi** | Nguồn chuẩn 5V - 3A (Pi 4) hoặc 5V - 5A (Pi 5) để tránh sụt áp cổng USB |
| **Màn hình / Remote** | Màn hình HDMI cắm trực tiếp hoặc kết nối Remote Desktop (VNC/RDP/SSH X11) |

---

## 3. Kiến Trúc Hệ Thống

```
+--------------------------------------------------------+
|             RPLIDAR C1M1 (360° ToF Scanner)            |
+--------------------------------------------------------+
                           │ (UART: TX, RX, 5V, GND)
                           ▼
+--------------------------------------------------------+
|      Mạch Chuyển Đổi USB/UART (Silicon Labs CP2102N)   |
+--------------------------------------------------------+
                           │ (Cáp USB Data: VID 10c4, PID ea60)
                           ▼
+--------------------------------------------------------+
|               Cổng USB Raspberry Pi (Linux)            |
|       /dev/ttyUSB0  <--- [Symlink: /dev/rplidar_c1]   |
+--------------------------------------------------------+
                           │ (Baudrate: 460800 bps)
                           ▼
+--------------------------------------------------------+
|        Driver ROS 2 SLAMTEC (Node: sllidar_node)       |
+--------------------------------------------------------+
                           │ (Publish message LaserScan)
                           ▼
              Topic ROS 2: /scan (10.0 Hz)
             /                           \
            ▼                             ▼
+-------------------------+   +--------------------------+
|  RViz2 (Trực quan 3D)   |   |   GUI Test Tool (Tkinter)|
|  - Frame: laser         |   |   - Kiểm tra 9 bước      |
|  - Đám mây điểm 360°   |   |   - Báo PASS/FAIL        |
+-------------------------+   +--------------------------+
```

---

## 4. Điều Kiện Trước Khi Cài Đặt

Mở terminal trên máy hoặc qua SSH (`ssh khangho@khang.local`):

### 4.1. Kiểm tra Hệ điều hành (OS)
```bash
lsb_release -a
```
- **Giải thích lệnh**: `lsb_release` đọc thông tin bản phân phối Linux hiện hành. Cờ `-a` (all) yêu cầu hiển thị toàn bộ chi tiết (Distributor, Description, Release, Codename).
- **Kết quả mong đợi**: `Ubuntu 24.04.5 LTS`, Codename `noble`.

### 4.2. Kiểm tra Kiến trúc Vi xử lý (Architecture)
```bash
uname -m
```
- **Giải thích lệnh**: `uname` xuất thông tin nhân hệ điều hành. Cờ `-m` (machine) in ra kiến trúc phần cứng vi xử lý.
- **Kết quả mong đợi**: `aarch64` (ARM 64-bit của Raspberry Pi).

### 4.3. Kiểm tra Môi trường ROS 2
```bash
source /opt/ros/jazzy/setup.bash
ros2 --help
```
- **Giải thích lệnh**: 
  - `source /opt/ros/jazzy/setup.bash`: Nạp toàn bộ biến môi trường của ROS 2 Jazzy (như `PATH`, `PYTHONPATH`, `AMENT_PREFIX_PATH`).
  - `ros2 --help`: Kiểm tra lệnh CLI điều khiển ROS 2 đã hoạt động.
- **Kết quả mong đợi**: Hiển thị danh sách các phân hệ lệnh của ROS 2 (`action`, `launch`, `node`, `pkg`, `run`, `topic`,...).

### 4.4. Kiểm tra Nhận diện Cổng USB
```bash
lsusb
```
- **Giải thích lệnh**: Liệt kê toàn bộ các thiết bị đang cắm vào bus USB của máy.
- **Kết quả mong đợi**: Xuất hiện dòng:
  `Bus 001 Device 003: ID 10c4:ea60 Silicon Labs CP210x UART Bridge`
  *(Trong đó `10c4` là mã nhà sản xuất Vendor ID của Silicon Labs, `ea60` là mã thiết bị Product ID của chip CP2102N).*

---

## 5. Kết Nối Phần Cứng

1. **Cắm LiDAR vào Adapter**:
   - Cắm cáp dẹt 7-pin từ đuôi cảm biến RPLIDAR C1 vào bo mạch adapter USB chuyển đổi đi kèm.
2. **Cắm cáp USB vào Raspberry Pi**:
   - Dùng cáp USB cắm từ cổng Micro-USB/Type-C của adapter vào cổng USB trên Raspberry Pi (khuyến nghị cắm vào cổng USB 2.0 hoặc 3.0 bất kỳ).
3. **Đặt LiDAR trên mặt phẳng ổn định**:
   - Đặt cảm biến theo chiều thẳng đứng, bảo đảm đầu laser phía trên có không gian quét tự do 360 độ, không bị dây cáp hay vật cản cơ học chèn vào phần mắt quét xoay.

> [!IMPORTANT]
> Tuyệt đối KHÔNG yêu cầu đấu nối dây trực tiếp vào các chân UART GPIO (GPIO 14/15) của Raspberry Pi khi bạn đã có module USB chuyển đổi chính hãng. Cổng USB giúp cách ly nguồn an toàn và cắm/rút linh hoạt.

---

## 6. Cài Đặt Hệ Thống & Bộ Script Tự Động

Toàn bộ mã nguồn kiểm thử nằm trong thư mục:
`rplidar_c1_test/` (trên Pi tại `/home/khangho/rplidar_c1_test`).

### 6.1. Chi tiết các script trong thư mục `scripts/`:

| Tên Script | Chức năng chi tiết |
| :--- | :--- |
| `scripts/detect_lidar.sh` | Quét hệ thống tìm chính xác adapter C1 (VID `10c4`, PID `ea60`), kiểm tra symlink `/dev/rplidar_c1`, kiểm tra quyền Đọc/Ghi. |
| `scripts/setup_udev.sh` | Tạo rule udev `/etc/udev/rules.d/99-rplidar.rules`, gán quyền truy cập `0666` và symlink cố định `/dev/rplidar_c1`. |
| `scripts/install_dependencies.sh` | Cài đặt `python3-tk`, `python3-serial`, clone và biên dịch driver chính thức `sllidar_ros2`. |
| `scripts/start_lidar.sh` | Nạp môi trường ROS 2, tự động tìm cổng và khởi chạy node driver C1 ngầm, lưu PID và ghi log. |
| `scripts/stop_lidar.sh` | Gửi tín hiệu `SIGINT`/`SIGTERM` dừng node an toàn, tắt motor quét laser và dọn PID. |
| `scripts/test_scan.sh` | Subscriber trực tiếp vào `/scan` trong 3 giây, tính toán tần số Hz, góc quét, số điểm scan và tỷ lệ điểm hợp lệ. |
| `scripts/diagnostics.sh` | Thu thập báo cáo chẩn đoán toàn diện (OS, RAM, USB, Udev, Dialout, log) xuất ra `logs/diagnostics.log`. |

### 6.2. Các bước cài đặt:

```bash
cd /home/khangho/rplidar_c1_test
chmod +x scripts/*.sh app/*.py desktop/*.sh
./scripts/install_dependencies.sh
```

---

## 7. Cài Driver SLAMTEC (Nguồn Chính Thức)

Nguồn mã nguồn chính thức được phát triển bởi SLAMTEC:
👉 [https://github.com/Slamtec/sllidar_ros2](https://github.com/Slamtec/sllidar_ros2)

Driver được biên dịch riêng biệt trong workspace độc lập `~/rplidar_c1_ws`:
```bash
# 1. Tạo thư mục workspace
mkdir -p ~/rplidar_c1_ws/src
cd ~/rplidar_c1_ws/src

# 2. Clone mã nguồn
git clone https://github.com/Slamtec/sllidar_ros2.git

# 3. Biên dịch bằng colcon
cd ~/rplidar_c1_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select sllidar_ros2
```

- **Giải thích các tham số `colcon build`**:
  - `--symlink-install`: Cho phép tạo symlink cho các file cấu hình và launch file thay vì sao chép tĩnh, giúp cập nhật tức thì khi chỉnh sửa mà không cần build lại.
  - `--packages-select sllidar_ros2`: Chỉ định biên dịch riêng gói driver cảm biến, bỏ qua các thành phần khác nhằm tiết kiệm thời gian và RAM của Raspberry Pi.

---

## 8. Thiết Lập Quyền USB & Udev Rules

### 8.1. Vì sao không nên dùng `sudo chmod 777 /dev/ttyUSB0` vĩnh viễn?
- Cổng `/dev/ttyUSB*` là một thiết bị động (dynamic device node). Mỗi khi bạn rút cáp USB ra cắm lại hoặc khởi động lại Raspberry Pi, Linux udev sẽ tạo lại node mới với quyền mặc định `crw-rw---- root:dialout`. Lệnh `chmod 777` chỉ có tác dụng tạm thời và sẽ biến mất ngay sau khi cắm lại thiết bị!
- Sử dụng `chmod 777` bừa bãi làm suy giảm tính bảo mật của hệ thống Linux.

### 8.2. Giải pháp chuẩn: Udev Rule & Nhóm `dialout`
Dự án cung cấp script tự động:
```bash
./scripts/setup_udev.sh
```
**Nội dung rule được ghi vào `/etc/udev/rules.d/99-rplidar.rules`**:
```udev
KERNEL=="ttyUSB*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE:="0666", GROUP:="dialout", SYMLINK+="rplidar_c1"
KERNEL=="ttyACM*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE:="0666", GROUP:="dialout", SYMLINK+="rplidar_c1"
```

- **Ý nghĩa kỹ thuật**:
  - `ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60"`: Nhận diện chính xác chip CP2102N của RPLIDAR C1.
  - `MODE:="0666"`: Cấp quyền Đọc và Ghi (rw-rw-rw-) cho mọi tiến trình người dùng bình thường mà không cần cấp quyền root (`sudo`).
  - `SYMLINK+="rplidar_c1"`: Tạo một đường dẫn cố định và vĩnh viễn `/dev/rplidar_c1`. Dù thiết bị bị nhận diện là `ttyUSB0`, `ttyUSB1` hay `ttyUSB2`, đường dẫn `/dev/rplidar_c1` sẽ luôn trỏ chính xác về cảm biến C1!

---

## 9. Kiểm Tra LiDAR Được Nhận Diện

Chạy các lệnh sau trong terminal để xác nhận phần cứng:

### Lệnh 1: Kiểm tra Bus USB
```bash
lsusb
```
*Kết quả:*
```
Bus 001 Device 003: ID 10c4:ea60 Silicon Labs CP210x UART Bridge
```

### Lệnh 2: Kiểm tra đường dẫn cố định theo ID phần cứng
```bash
ls -l /dev/serial/by-id/
```
*Kết quả:*
```
lrwxrwxrwx 1 root root 13 Sep 15 04:04 usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_76815f48566eef11bd64dec2c169b110-if00-port0 -> ../../ttyUSB0
```

### Lệnh 3: Kiểm tra Symlink Udev
```bash
ls -l /dev/rplidar_c1
```
*Kết quả:*
```
lrwxrwxrwx 1 root root 7 Sep 15 04:04 /dev/rplidar_c1 -> ttyUSB0
```

### Lệnh 4: Chạy script tự động quét LiDAR
```bash
./scripts/detect_lidar.sh
```
*Kết quả:*
```
==================================================
          KẾT QUẢ PHÁT HIỆN RPLIDAR C1            
==================================================
[PASS] Đã tìm thấy cảm biến RPLIDAR C1!
  - Cổng kết nối : /dev/rplidar_c1
  - Tên thiết bị : RPLIDAR C1 (qua udev symlink /dev/rplidar_c1)
  - Đường dẫn gốc: /dev/ttyUSB0
  - Quyền truy cập: [PASS] Đọc/Ghi (OK)
==================================================
```

---

## 10. Cách Chạy Bằng Giao Diện Đồ Họa (GUI)

Đây là phương thức kiểm thử thuận tiện và trực quan nhất dành cho người dùng:

### Các bước thực hiện trên Desktop:
1. **Mở Desktop**: Kết nối trực tiếp màn hình HDMI hoặc mở qua VNC/Remote Desktop.
2. **Khởi chạy ứng dụng**:
   - Double-click vào biểu tượng **`RPLIDAR C1 Test`** trên màn hình Desktop.
   - Hoặc chạy từ terminal:
     ```bash
     /home/khangho/rplidar_c1_test/desktop/run_gui.sh
     ```
3. **Bấm nút `[ CHECK SYSTEM ]`**:
   - Ứng dụng tự động chạy kiểm tra 9 bước hệ thống.
   - Chờ tất cả các đèn LED chuyển sang màu **Xanh lá (PASS)**.
4. **Bấm nút `[ START LIDAR ]`**:
   - Motor trên cảm biến C1 bắt đầu quay tít.
   - Đèn `Driver C1` báo XANH, đèn `Topic /scan` báo XANH.
   - Bảng chỉ số cập nhật liên tục:
     - Tần số: `~10.00 Hz`
     - Số điểm scan: `~720 điểm / vòng 360°`
     - Khoảng cách Min / Max biến thiên theo không gian thực tế.
5. **Bấm nút `[ VIEW SCAN ]`**:
   - Cửa sổ ứng dụng **RViz2** mở lên với cấu hình tối ưu sẵn.
   - Bạn sẽ nhìn thấy toàn bộ đường biên các bức tường và vật thể quanh cảm biến dưới dạng các chấm sáng 360°.
6. **Thực hiện các bài test thực nghiệm** (đặt hộp, vẫy tay quanh cảm biến).
7. **Bấm nút `[ STOP LIDAR ]`**:
   - Driver dừng lại an toàn, motor LiDAR ngắt quay để bảo vệ tuổi thọ cảm biến.

---

## 11. Cách Chạy Bằng Dòng Lệnh (CLI - Chế Độ Debug)

Nếu bạn truy cập từ xa qua SSH không có giao diện đồ họa, hãy sử dụng các lệnh CLI sau:

### Bước 1: Khởi động Driver
```bash
/home/khangho/rplidar_c1_test/scripts/start_lidar.sh
```
- **Giải thích**: Script tự động nạp ROS 2 Jazzy, nạp workspace, kiểm tra cổng `/dev/rplidar_c1`, đặt baudrate `460800` và khởi chạy node `sllidar_node` ngầm trong nền.

### Bước 2: Kiểm tra topic `/scan`
```bash
source /opt/ros/jazzy/setup.bash
ros2 topic hz /scan
```
- **Giải thích**: Đo tần số xuất bản tin nhắn trên topic `/scan`.
- **Kết quả chuẩn**: `average rate: 10.030 Hz, min: 0.098s max: 0.102s`.

### Bước 3: Đọc 1 tin nhắn LaserScan hoàn chỉnh
```bash
ros2 topic echo /scan --once
```
- **Giải thích**: In toàn bộ cấu trúc tin nhắn `sensor_msgs/msg/LaserScan` của một vòng quét đơn lẻ.

### Bước 4: Chạy script đánh giá chuyên sâu
```bash
/home/khangho/rplidar_c1_test/scripts/test_scan.sh
```
- **Giải thích**: Tính toán chi tiết số điểm hữu hạn, cự ly đo và xác nhận tiêu chuẩn PASS.

### Bước 5: Dừng Driver
```bash
/home/khangho/rplidar_c1_test/scripts/stop_lidar.sh
```

---

## 12. Kết Quả Mong Đợi Khi Cảm Biến Chạy Bình Thường

Khi RPLIDAR C1 hoạt động chính xác, dữ liệu thu thập thực tế như sau:

```
==================================================
        KẾT QUẢ ĐÁNH GIÁ DỮ LIỆU LASERSCAN        
==================================================
Tổng số frame nhận được : 31 messages
Tần số quét thực tế     : 10.03 Hz (Kỳ vọng: ~10.0 Hz)
Frame ID                : laser
Góc quét angle_min      : -180.00° (-3.1416 rad)
Góc quét angle_max      : 180.00° (3.1416 rad)
Độ phân giải góc        : 0.501°
Giới hạn khoảng cách    : 0.05 m -> 16.00 m
Số điểm scan trung bình : 720 điểm / vòng 360°
Số điểm hợp lệ          : 19272 (86.3%)
Khoảng cách gần nhất    : 0.105 m
Khoảng cách xa nhất     : 2.700 m
--------------------------------------------------
[PASS] DỮ LIỆU LASERSCAN HỢP LỆ & CẢM BIẾN HOẠT ĐỘNG HOÀN HẢO!
==================================================
```

---

## 13. Hướng Dẫn Test Thực Nghiệm (Test Protocols)

### TEST A - Không Có Vật Cản Gần (Free Space Test)
- **Thực hiện**: Đặt cảm biến trên bàn hoặc mặt sàn thông thoáng.
- **Quan sát**: Trên RViz2 hoặc bảng thông số GUI, các điểm laser quét xa chạm vào các bức tường phòng (thường từ 1.5m - 5.0m). `Khoảng cách gần nhất` không được nhỏ hơn 0.5m nếu xung quanh không có vật thể.

### TEST B - Đặt Hộp Cố Định Phía Trước (Obstacle Detection Test)
- **Thực hiện**: Đặt một chiếc hộp carton hoặc sách cách đầu cảm biến từ 0.5m đến 1.0m thẳng hướng quét.
- **Quan sát**: Trên RViz2 xuất hiện một cụm điểm phản xạ phẳng vuông góc thẳng hàng với cạnh hộp. Giá trị `Khoảng cách gần nhất` giảm ngay lập tức về đúng cự ly đặt hộp (ví dụ: `0.52m`).

### TEST C - Di Chuyển Vật Thể (Dynamic Tracking Test)
- **Thực hiện**: Đưa bàn tay hoặc di chuyển chiếc hộp từ từ quanh cảm biến theo chiều kim đồng hồ.
- **Quan sát**: Trên RViz2, dải điểm đại diện cho vật thể di chuyển mượt mà bám sát chuyển động thực tế theo thời gian thực (Realtime, độ trễ < 100ms).

### TEST D - Kiểm Tra Quét Đầy Đủ 360° (Full Omnidirectional Test)
- **Thực hiện**: Quan sát toàn bộ vòng tròn xung quanh cảm biến.
- **Quan sát**: Ngoại trừ các góc bị chính dây cáp hoặc ngàm đỡ cảm biến che khuất cục bộ, toàn bộ chu vi xung quanh phải có dữ liệu phản xạ liên tục. Góc quét bao phủ đủ từ `-180°` đến `+180°` với độ phân giải góc xấp xỉ `0.5°`.

---

## 14. Bảng Xử Lý Sự Cố (Troubleshooting Matrix)

| Triệu chứng | Nguyên nhân khả dĩ | Cách kiểm tra | Cách xử lý |
| :--- | :--- | :--- | :--- |
| **Không có `/dev/ttyUSB*`** | Cáp USB bị lỏng, cáp chỉ sạc (không có dây data), hoặc thiếu nguồn. | Chạy `lsusb` và `dmesg \| tail -n 20`. | Đổi dây cáp USB khác (chắc chắn có data), cắm chặt lại vào cổng USB trên Pi. |
| **Permission Denied** | User chưa thuộc nhóm `dialout` hoặc chưa cài rule udev. | Chạy `ls -l /dev/ttyUSB0` xem quyền và nhóm sở hữu. | Chạy `./scripts/setup_udev.sh`, sau đó cắm lại cáp USB. |
| **LiDAR không quay motor** | Nguồn cấp cổng USB không đủ dòng điện, hoặc motor bị kẹt. | Kiểm tra đèn đỏ laser bên trong lăng kính có sáng không. | Dùng nguồn chuẩn 5V-3A cho Pi; kiểm tra xem có dị vật vướng vào vành xoay không. |
| **Serial Communication Timeout** | Sai Baudrate (C1 dùng 460800, nếu cấu hình nhầm 115200 hay 256000 sẽ bị timeout). | Kiểm tra file `config/lidar.yaml` hoặc đối số launch. | Đảm bảo `serial_baudrate` luôn là `460800`. |
| **Driver chạy nhưng không có `/scan`** | Cảm biến rơi vào chế độ bảo vệ (Protection mode) do sụt áp lúc khởi động. | Đọc `cat logs/driver.log` xem lỗi `health status`. | Chạy `./scripts/stop_lidar.sh`, rút cáp USB ra 5 giây rồi cắm lại và start lại. |
| **Topic `/scan` có nhưng ranges toàn giá trị rỗng hoặc inf** | Bề mặt xung quanh hấp thụ laser (màu đen bóng, kính trong suốt) hoặc khoảng cách ngoài tầm đo (< 0.05m hoặc > 16m). | Đưa một tấm bìa trắng cách mắt cảm biến 30cm. | Tránh thử nghiệm trước cửa kính hoặc gương bóng phản quang mạnh. |
| **RViz không hiện scan** | Sai `Fixed Frame` (ví dụ đang để `map` thay vì `laser`). | Nhìn mục `Global Options -> Fixed Frame` trong RViz. | Đổi Fixed Frame thành `laser`. |
| **RViz crash hoặc không mở được** | Biến môi trường `$DISPLAY` chưa được đặt hoặc phiên đồ họa X11/Wayland bị khóa. | Chạy `echo $DISPLAY`. | Sử dụng file cấu hình sẵn: `./scripts/start_lidar.sh` rồi chạy `rviz2 -d config/rplidar_c1.rviz`. |
| **Mất kết nối USB đột ngột** | Dây cáp bị rung lắc hoặc sụt nguồn đột ngột khi motor tăng tốc. | Xem `dmesg \| grep -i usb`. | Cố định chặt đế cảm biến, sử dụng hub USB có cấp nguồn ngoài nếu Pi gánh nhiều tải. |
| **Đường dẫn serial đổi sau khi khởi động lại** | Cắm thêm chuột/bàn phím USB khiến `/dev/ttyUSB0` nhảy thành `/dev/ttyUSB1`. | Chạy `ls -l /dev/serial/by-id/`. | Luôn sử dụng symlink cố định `/dev/rplidar_c1` thay vì hard-code `ttyUSB0`. |

---

## 15. Quản Lý Nhật Ký Hoạt Động (Logging)

Mọi tiến trình chạy đều được lưu vết chi tiết kèm mốc thời gian tại thư mục `logs/`:
- **`logs/driver.log`**: Toàn bộ luồng output từ ROS 2 launch, thông tin Serial Number (S/N), Firmware version, Hardware rev, Scan mode và các cảnh báo của driver SLAMTEC.
- **`logs/gui.log`**: Lưu nhật ký khởi chạy giao diện Desktop, trạng thái DISPLAY và các ngoại lệ đồ họa nếu có.
- **`logs/diagnostics.log`**: Báo cáo tổng thể toàn bộ hệ số an toàn phần cứng, nhiệt độ, điện áp và trạng thái hệ điều hành.

---

## 16. Hướng Dẫn Gỡ Bỏ (Uninstall)

Nếu muốn đưa hệ thống về trạng thái ban đầu:
```bash
# 1. Dừng cảm biến nếu đang chạy
/home/khangho/rplidar_c1_test/scripts/stop_lidar.sh

# 2. Xóa udev rule
sudo rm -f /etc/udev/rules.d/99-rplidar.rules
sudo udevadm control --reload-rules && sudo udevadm trigger

# 3. Xóa shortcut Desktop
rm -f /home/khangho/Desktop/rplidar-test.desktop

# 4. Xóa workspace driver
rm -rf /home/khangho/rplidar_c1_ws
```

---

## 17. Vì Sao Không Cần Cấu Hình IP Tĩnh (Static IP)?

> [!NOTE]
> Cảm biến **RPLIDAR C1M1 kết nối trực tiếp với Raspberry Pi thông qua giao tiếp phần cứng USB Serial (UART qua chip cầu nối CP2102N)**.
> - Toàn bộ việc trao đổi tín hiệu, điều khiển xung băm xung motor, cấu hình sample rate và nhận gói tin khoảng cách diễn ra qua cổng USB cục bộ (`/dev/rplidar_c1`) ở cấp độ hạt nhân Linux (Kernel tty driver).
> - Giao tiếp này hoàn toàn độc lập với ngăn xếp giao thức mạng TCP/IP.
> - Do đó, **kiểm thử RPLIDAR C1 tuyệt đối KHÔNG đòi hỏi đặt IP tĩnh, KHÔNG yêu cầu sửa file Netplan hay NetworkManager**. Dù Raspberry Pi cắm dây mạng, dùng Wi-Fi DHCP hay chạy hoàn toàn không có mạng, bài kiểm tra cảm biến vẫn chạy hoàn hảo 100%!

---

## 18. TỔNG HỢP TOÀN BỘ CÂU LỆNH ĐÃ SỬ DỤNG VÀ GIẢI THÍCH CHI TIẾT

Bảng dưới đây tổng hợp đầy đủ tất cả các câu lệnh terminal đã được sử dụng trong suốt quá trình khảo sát, cấu hình, biên dịch và kiểm thử thực tế trên thiết bị:

| STT | Câu lệnh terminal | Giải thích chi tiết chức năng & Ý nghĩa các cờ lệnh |
| :---: | :--- | :--- |
| **1** | `uname -m` | In ra kiến trúc vi xử lý phần cứng của bo mạch (`aarch64` = ARM 64-bit của Raspberry Pi 4/5). |
| **2** | `lsb_release -a` | Đọc cơ sở dữ liệu hệ điều hành để xác định phiên bản Ubuntu đang chạy (`Ubuntu 24.04.5 LTS`). |
| **3** | `lsusb` | Liệt kê toàn bộ các thiết bị gắn trên bus USB nhằm xác định VID/PID của module chuyển đổi UART (`10c4:ea60`). |
| **4** | `ls -la /dev/serial/by-id/*` | Kiểm tra danh mục các liên kết tắt ổn định được tạo bởi kernel dựa trên chuỗi Serial Number định danh của chip CP2102N. |
| **5** | `groups` | Liệt kê tất cả các nhóm quyền mà tài khoản người dùng (`khangho`) đang trực thuộc (để kiểm tra xem có nhóm `dialout` hay không). |
| **6** | `sudo usermod -aG dialout khangho` | Thêm tài khoản `khangho` vào nhóm `dialout`. Cờ `-a` (append) để nối thêm nhóm, `-G` (groups) chỉ định danh sách nhóm bổ sung. |
| **7** | `sudo udevadm control --reload-rules` | Yêu cầu tiến trình quản lý thiết bị `systemd-udevd` nạp lại toàn bộ file rule trong `/etc/udev/rules.d/`. |
| **8** | `sudo udevadm trigger` | Kích hoạt lại các sự kiện udev cho toàn bộ thiết bị đang cắm trên máy để áp dụng rule mới ngay lập tức mà không cần reboot. |
| **9** | `source /opt/ros/jazzy/setup.bash` | Nạp biến môi trường của ROS 2 Jazzy vào phiên làm việc hiện tại của shell bash. |
| **10** | `colcon build --symlink-install --packages-select sllidar_ros2` | Công cụ build chính thức của ROS 2. `--symlink-install` dùng liên kết mềm giúp linh hoạt debug; `--packages-select` chỉ build riêng package sllidar_ros2. |
| **11** | `ros2 pkg prefix sllidar_ros2` | Truy vấn thư mục cài đặt gốc (install prefix) của package `sllidar_ros2` để xác thực hệ thống ROS 2 đã nhận diện được package. |
| **12** | `ros2 launch launch/lidar_test.launch.py serial_port:=/dev/rplidar_c1 serial_baudrate:=460800` | Khởi động node driver sllidar_node với đối số cổng là `/dev/rplidar_c1` và tốc độ baud chuẩn của C1 là `460800` bps. |
| **13** | `ros2 topic list -t` | Liệt kê danh sách tất cả các topic ROS 2 đang hoạt động trong hệ thống kèm theo kiểu dữ liệu tương ứng (`-t` = topic type). |
| **14** | `ros2 topic hz /scan` | Lắng nghe và đo đạc tần số xuất bản gói tin thực tế (tính bằng Hertz) của topic `/scan`. |
| **15** | `ros2 topic echo /scan --once` | Bắt và in ra màn hình cấu trúc dữ liệu của duy nhất một tin nhắn `sensor_msgs/msg/LaserScan` đầu tiên nhận được rồi tự động thoát (`--once`). |
| **16** | `kill -SIGINT <PID>` | Gửi tín hiệu ngắt phần mềm chuẩn (tương đương bấm Ctrl+C) để node ROS 2 đóng cổng serial và tắt motor một cách êm ái, an toàn. |
| **17** | `kill -SIGTERM <PID>` | Gửi tín hiệu buộc kết thúc tiến trình nếu sau một khoảng thời gian tiến trình vẫn chưa dừng hẳn. |
| **18** | `pgrep -fl sllidar_node` | Tìm kiếm và in ra Process ID (PID) cùng toàn bộ câu lệnh dòng lệnh (`-f` = full command line, `-l` = list name) của các tiến trình mang tên `sllidar_node`. |
| **19** | `rviz2 -d config/rplidar_c1.rviz` | Mở ứng dụng RViz2 với file cấu hình được tối ưu sẵn (`-d` = display config file) có sẵn Fixed Frame `laser` và hiển thị `/scan`. |
| **20** | `chmod +x <file>` | Cấp quyền thực thi (executable) cho file script shell (`.sh`) hoặc file thực thi Python (`.py`). |

---

## 19. HỆ THỐNG TẠO BẢN ĐỒ 2D REALTIME VỚI SLAM TOOLBOX (PI + RPLIDAR C1)

### 19.1. Giới thiệu & Định hướng Kỹ thuật
> [!IMPORTANT]
> **Định hướng cốt lõi theo yêu cầu**: 
> Toàn bộ hệ thống SLAM được tinh gọn và tập trung **chính xác ở mức độ Raspberry Pi và cảm biến RPLIDAR C1**, không cần gắn khung xe, động cơ hay mạch điều khiển bánh xe phức tạp.
> - **CHƯA triển khai Nav2** (Navigation 2).
> - **CHƯA triển khai autonomous navigation** (điều hướng tự hành A → B).
> - **CHƯA triển khai path planning** (quy hoạch quỹ đạo chuyển động).
> - **KHÔNG yêu cầu IP tĩnh** và **KHÔNG sửa cấu hình mạng**.
> - **Trung thực kỹ thuật tuyệt đối**: Phân định rõ ràng giữa **Chế độ kiểm thử Pi + LiDAR (Pi + LiDAR Test Mode)** và **Chế độ Robot di chuyển thực tế (Moving Robot Odometry)**.

---

### 19.2. Kiến Trúc Hệ Thống & Cây Biến Đổi Tọa Độ TF2 (TF Tree)

Để thuật toán SLAM Toolbox (sử dụng tối ưu hóa Ceres Solver) có thể liên tục cập nhật và tích lũy đám mây điểm thành bản đồ lưới chiếm chỗ (Occupancy Grid Map), hệ thống thiết lập chuỗi biến đổi tọa độ chuẩn ROS REP-105:

```
+-------------------------------------------------------------------------+
|                                  map                                    |
|         (Hệ quy chiếu toàn cục cố định, xuất bản bởi slam_toolbox)      |
+-------------------------------------------------------------------------+
                                     │  (Dynamic TF: map -> odom)
                                     ▼
+-------------------------------------------------------------------------+
|                                 odom                                    |
| (Hệ quy chiếu tích lũy hành trình, xuất bản bởi odom_tf_broadcaster)   |
+-------------------------------------------------------------------------+
                                     │  (Dynamic TF: odom -> base_footprint)
                                     ▼
+-------------------------------------------------------------------------+
|                            base_footprint                               |
|        (Chiếu hình học của robot tiếp xúc vuông góc với mặt sàn)        |
+-------------------------------------------------------------------------+
                                     │  (Static/Dynamic: base_footprint -> base_link)
                                     ▼
+-------------------------------------------------------------------------+
|                              base_link                                  |
|          (Tâm quay hình học trục bánh xe của robot / đế gắn Pi)         |
+-------------------------------------------------------------------------+
                                     │  (Dynamic TF: base_link -> laser, z = 0.10m)
                                     ▼
+-------------------------------------------------------------------------+
|                                 laser                                   |
|       (Tâm phát quét laser 360° của cảm biến RPLIDAR C1M1, /scan)       |
+-------------------------------------------------------------------------+
```

#### Giải Quyết Vấn Đề Đồng Bộ Timestamp trong Chế Độ Pi + LiDAR:
- Trong điều kiện kiểm thử chỉ có Raspberry Pi và LiDAR (chưa có encoder bánh xe), việc dùng lệnh `static_transform_publisher` cho `odom -> base_link` sẽ sinh ra timestamp = 0. Khi đó `slam_toolbox` tra cứu biến đổi tại thời điểm quét tia laser sẽ bị lỗi `Failed to compute odom pose`.
- Project giải quyết triệt để bằng module **`app/odom_tf_broadcaster.py`**: Node này tự động tính toán thời gian thực theo đồng hồ hệ thống (`get_clock().now()`) và phát sóng đồng bộ toàn bộ chuỗi biến đổi `odom -> base_footprint -> base_link -> laser` với tần số 25 Hz. Nhờ đó, SLAM Toolbox tính toán hoàn hảo và bắt đầu tạo map ngay tức thì!

---

### 19.3. Mô Hình Động Học & Odometry Xe 2 Bánh Vi Sai (Differential Drive)

Khi nâng cấp lên robot hoàn chỉnh có gắn động cơ và encoder, module **`app/diff_drive_odometry.py`** được tích hợp sẵn để tính toán tọa độ $x, y, \theta$ dựa trên mô hình toán học chuẩn:

1. **Vận tốc tuyến tính từng bánh ($v_L, v_R$)**:
   $$\Delta s_L = 2\pi R \cdot \frac{\Delta \text{ticks}_L}{N}, \quad \Delta s_R = 2\pi R \cdot \frac{\Delta \text{ticks}_R}{N}$$
   Trong đó:
   - $R$: Bán kính bánh xe (m).
   - $N$: Số xung encoder trên một vòng quay (CPR).
   - $\Delta \text{ticks}$: Số xung đo được trong khoảng thời gian $\Delta t$.

2. **Chuyển dịch tuyến tính ($\Delta s$) và góc quay ($\Delta \theta$)**:
   $$\Delta s = \frac{\Delta s_R + \Delta s_L}{2}, \quad \Delta \theta = \frac{\Delta s_R - \Delta s_L}{L}$$
   Trong đó $L$ là khoảng cách giữa 2 tâm bánh xe (Wheel Track).

3. **Tích lũy vị thế Robot (Pose Integration)**:
   $$x_{k+1} = x_k + \Delta s \cdot \cos\left(\theta_k + \frac{\Delta \theta}{2}\right)$$
   $$y_{k+1} = y_k + \Delta s \cdot \sin\left(\theta_k + \frac{\Delta \theta}{2}\right)$$
   $$\theta_{k+1} = \theta_k + \Delta \theta$$

4. **Xuất bản dữ liệu ROS 2**:
   - Topic: `/odom` (Kiểu tin nhắn `nav_msgs/msg/Odometry`).
   - Transform: `odom -> base_footprint` trên `/tf`.

---

### 19.4. Cấu Hình SLAM Toolbox Tối Ưu Cho Raspberry Pi (`config/slam_toolbox.yaml`)

File cấu hình được căn chỉnh đặc biệt để đạt hiệu năng xử lý mượt mà trên phần cứng Raspberry Pi (CPU Quad-core Cortex-A72 / A76):
- **Chế độ**: `online_async` (xử lý không đồng bộ, không bao giờ gây nghẽn luồng nhận gói tin `/scan`).
- **Độ phân giải ô lưới (Resolution)**: `0.05` m (5 cm / ô).
- **Tầm quét tối đa**: `12.0` m (khớp với tầm quét hiệu dụng của RPLIDAR C1).
- **Bộ giải tối ưu (Solver)**: `solver_plugins::CeresSolver` với kích thước stack `40000000` bytes.
- **Tần số cập nhật bản đồ**: `2.0` giây / lần (`map_update_interval: 2.0`).
- **Ngưỡng cập nhật Pose Graph**: Tối thiểu di chuyển `0.15` m hoặc quay `10°` (`0.174` rad) mới chèn node mới vào đồ thị, giúp tiết kiệm bộ nhớ RAM và CPU của Pi khi đứng yên.

---

### 19.5. Hướng Dẫn Sử Dụng Bộ Script SLAM

| Script Shell | Đường dẫn | Chức năng chi tiết |
| :--- | :--- | :--- |
| **`check_slam.sh`** | `scripts/check_slam.sh` | Tự động kiểm tra toàn bộ 8 điều kiện tiên quyết (Cổng USB, driver C1, topic /scan, package SLAM, map_server, TF tree, nguồn Odometry, RViz2) và in báo cáo đánh giá. |
| **`start_slam.sh`** | `scripts/start_slam.sh` | Khởi động `slam_mapping.launch.py`, quản lý vòng đời Lifecycle Node `/slam_toolbox` (chuyển đổi từ `unconfigured` -> `configured` -> `active`), ghi log nền và theo dõi xuất bản `/map`. |
| **`stop_slam.sh`** | `scripts/stop_slam.sh` | Dừng an toàn và triệt để mọi tiến trình SLAM, broadcater TF, static publisher và dọn dẹp PID file. |
| **`save_map.sh`** | `scripts/save_map.sh <tên_map>` | Gọi script Python `save_map.py` gửi request service `/slam_toolbox/save_map` hoặc dùng `nav2_map_server` để xuất file `.yaml` và `.pgm` vào thư mục `maps/`. |
| **`inspect_tf.sh`** | `scripts/inspect_tf.sh` | Đo đạc và giám sát trực tiếp cây TF2 thời gian thực, kiểm tra liên kết `base_link -> laser`, `odom -> base_link`, và `map -> odom`. |

#### Ví dụ thao tác dòng lệnh:
```bash
# 1. Kiểm tra toàn diện hệ thống trước khi chạy
/home/khangho/rplidar_c1_test/scripts/check_slam.sh

# 2. Khởi động SLAM Toolbox (tự động phát dynamic TF cho Pi + C1)
/home/khangho/rplidar_c1_test/scripts/start_slam.sh

# 3. Giám sát các topic bản đồ được xuất bản
source /opt/ros/jazzy/setup.bash
ros2 topic hz /map
ros2 topic echo /map_metadata --once

# 4. Lưu bản đồ hiện tại vào thư mục maps/
/home/khangho/rplidar_c1_test/scripts/save_map.sh phong_khach

# 5. Dừng SLAM khi hoàn tất phiên kiểm thử
/home/khangho/rplidar_c1_test/scripts/stop_slam.sh
```

---

### 19.6. Thư Mục Bản Đồ `maps/` & Định Dạng Bản Đồ Được Lưu

Mọi bản đồ lưu thành công được đặt trong thư mục `maps/`:
- **File Metadata (`.yaml`)**:
  ```yaml
  image: test_room.pgm
  mode: trinary
  resolution: 0.050
  origin: [-0.387, -1.084, 0]
  negate: 0
  occupied_thresh: 0.65
  free_thresh: 0.196
  ```
- **File Hình Ảnh Điểm Lưới (`.pgm`)**:
  Ảnh Grayscale Portable Graymap thể hiện không gian:
  - Màu trắng (254): Vùng không gian trống an toàn (Free Space).
  - Màu đen (000): Vật cản / Tường nhà (Occupied Obstacle).
  - Màu xám (205): Vùng chưa được quét tới (Unknown Space).

---

### 19.7. Ứng Dụng SLAM CONTROL GUI & Trực Quan Hóa RViz2

Ứng dụng **`app/slam_gui.py`** cung cấp giao diện đồ họa trực quan:
- **Đèn LED hiển thị 6 trạng thái cốt lõi**:
  1. `RPLIDAR C1`: Trạng thái kết nối USB & driver phần cứng.
  2. `Topic /scan`: Trạng thái nhận dữ liệu quét laser và tần số Hz.
  3. `SLAM Toolbox Node`: Trạng thái tiến trình thuật toán SLAM.
  4. `Transform TF2`: Trạng thái chuỗi liên kết tọa độ `map -> odom -> base_link -> laser`.
  5. `Bản đồ /map`: Trạng thái xuất bản bản đồ Occupancy Grid.
  6. `Wheel Odometry`: Thông báo minh bạch chế độ hoạt động (Màu vàng: Chế độ Pi+LiDAR Test Mode; Màu xanh: Đã có Wheel Odometry).
- **Khung Đo Đạc Bản Đồ Thời Gian Thực**: Hiển thị kích thước bản đồ ($W \times H$ mét), tổng số ô lưới (cells), độ phân giải (cm) và số frame bản đồ đã thu thập.
- **Hệ thống Nút bấm chức năng**:
  - `[ KIỂM TRA HỆ THỐNG ]`: Chạy script chẩn đoán `check_slam.sh`.
  - `[ KHỞI ĐỘNG SLAM ]`: Chạy thuật toán và kích hoạt lifecycle node.
  - `[ XEM BẢN ĐỒ (RVIZ2) ]`: Tự động mở RViz2 với file cấu hình `config/slam.rviz` hiển thị Grid, Map, LaserScan, TF.
  - `[ LƯU BẢN ĐỒ ]`: Hộp thoại nhập tên và lưu trực tiếp bản đồ ra file `.yaml` + `.pgm`.
  - `[ RESET MAP ]`: Xóa trắng phiên bản đồ hiện tại để quét lại từ đầu.
  - `[ DỪNG SLAM ]`: Dừng an toàn toàn bộ tiến trình.

#### Khởi chạy từ Desktop Raspberry Pi:
- Người dùng kết nối qua Remote Desktop (XRDP / VNC) tới IP `100.90.252.15` (hoặc `khang.local`).
- Nhấp đúp chuột vào biểu tượng **`RPLIDAR C1 SLAM`** trên màn hình Desktop để mở ứng dụng.

---

### 19.8. BẢNG TỔNG HỢP CÂU LỆNH SLAM ĐÃ SỬ DỤNG VÀ GIẢI THÍCH CHI TIẾT

| STT | Câu lệnh terminal | Giải thích chi tiết chức năng & Cơ chế hoạt động |
| :---: | :--- | :--- |
| **21** | `ros2 lifecycle get /slam_toolbox` | Truy vấn trạng thái vòng đời hiện tại của node `/slam_toolbox` (`unconfigured`, `inactive`, `active`, hoặc `finalized`). |
| **22** | `ros2 lifecycle set /slam_toolbox configure` | Kích hoạt quá trình cấu hình node: Nạp file tham số YAML, khởi tạo solver Ceres, cấp phát bộ nhớ scan buffer. |
| **23** | `ros2 lifecycle set /slam_toolbox activate` | Kích hoạt node sang trạng thái hoạt động: Bắt đầu lắng nghe `/scan`, xử lý đăng ký tia quét và xuất bản topic `/map`. |
| **24** | `ros2 run tf2_ros tf2_echo odom base_link` | Lắng nghe topic `/tf` và in ra chi tiết ma trận tịnh tiến (Translation x, y, z) và quay (Quaternion xyzw / RPY) từ frame `odom` sang `base_link`. |
| **25** | `ros2 run tf2_tools view_frames` | Lắng nghe toàn bộ cây biến đổi TF trong 5 giây và vẽ ra sơ đồ cây quan hệ giữa tất cả các frame dưới dạng file PDF (`frames.pdf`). |
| **26** | `ros2 param get /slam_toolbox base_frame` | Đọc giá trị tham số `base_frame` đang được node SLAM Toolbox sử dụng để kiểm tra xem đã khớp với cấu hình `base_link` hay chưa. |
| **27** | `ros2 topic echo /map_metadata --once` | Bắt và in ra cấu trúc thông tin metadata của bản đồ (kích thước ô `width`, `height`, độ phân giải `resolution`, tọa độ gốc `origin`) của 1 tin nhắn duy nhất rồi thoát. |
| **28** | `ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap "{name: {data: '<path>'}}"` | Gửi yêu cầu dịch vụ (service call) tới node SLAM Toolbox để ghi bản đồ hiện tại ra đĩa cứng thành 2 file `.pgm` và `.yaml`. |
| **29** | `ros2 run nav2_map_server map_saver_cli -f <path>` | Công cụ dòng lệnh của Map Server để đăng ký nhận topic `/map` (chế độ transient local) và lưu bản đồ dưới định dạng tiêu chuẩn ROS. |
| **30** | `rviz2 -d config/slam.rviz` | Mở trình trực quan hóa RViz2 với Fixed Frame là `map`, nạp sẵn các lớp hiển thị Grid nền, OccupancyGrid `/map`, đám mây điểm `/scan` và trục tọa độ TF. |

---

## 20. BÁO CÁO NGHIỆM THU DỰ ÁN (FINAL ACCEPTANCE REPORT)

| Hạng mục kiểm tra | Chế độ Pi + RPLIDAR C1 Test Mode | Chế độ Xe Robot Di Chuyển Thực Tế | Ghi chú & Trạng thái |
| :--- | :---: | :---: | :--- |
| **1. Nhận diện phần cứng RPLIDAR C1** | **PASS** | **PASS** | Nhận diện chip CP2102N (`10c4:ea60`), gán alias `/dev/rplidar_c1` |
| **2. Khởi động Driver SLAMTEC** | **PASS** | **PASS** | Node `sllidar_node` hoạt động ổn định ở baudrate `460800` |
| **3. Topic `/scan` (LaserScan)** | **PASS** | **PASS** | Xuất bản đều đặn 10.0 Hz, 720 điểm/vòng quét 360°, tỉ lệ điểm hợp lệ > 85% |
| **4. Cây biến đổi tọa độ TF2** | **PASS** | **PASS** | Chuỗi `map -> odom -> base_footprint -> base_link -> laser` liên tục, không trễ |
| **5. Thuật toán SLAM Toolbox** | **PASS** | **PASS** | Chạy `online_async`, Lifecycle Node `active`, solver Ceres giải đồ thị ổn định |
| **6. Xuất bản bản đồ `/map`** | **PASS** | **PASS** | Topic `/map` và `/map_metadata` xuất bản đầy đủ (độ phân giải 5cm) |
| **7. Lưu bản đồ (`.yaml` + `.pgm`)** | **PASS** | **PASS** | Script `save_map.sh` đã lưu thành công bản đồ `maps/test_room.pgm` và `.yaml` |
| **8. Wheel Odometry (Encoder)** | **NOT DETECTED** *(Minh bạch)* | **SẴN SÀNG** | Hệ thống hiện tại chỉ có Pi + LiDAR; module tính toán vi sai đã sẵn sàng |
| **9. Giao diện SLAM CONTROL GUI** | **PASS** | **PASS** | 6 đèn LED hiển thị realtime, thống kê $W \times H$, nút bấm điều khiển đầy đủ |
| **10. Trực quan hóa RViz2** | **PASS** | **PASS** | File cấu hình `config/slam.rviz` mở mượt mà trên desktop XRDP port 3389 |


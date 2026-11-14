# Ghi Chú Kỹ Thuật: LaserScan vs SLAM Mapping (Tùy Chọn Mở Rộng)

## 1. Nguyên Tắc Cốt Lõi: Đừng Đánh Đồng LaserScan và Bản Đồ SLAM
- **Project này là:** Công cụ kiểm tra phần cứng và luồng dữ liệu 2D Laser Range Scanner (**RPLIDAR C1M1**).
- Dữ liệu cảm biến trả về là `sensor_msgs/msg/LaserScan`: Một mảng các khoảng cách đo được tại các góc quét quanh tâm cảm biến trong hệ quy chiếu cục bộ `laser`.
- **LaserScan KHÔNG PHẢI là Bản đồ (Occupancy Grid Map)**. 
- LaserScan chỉ thể hiện vị trí các điểm phản xạ tại một thời điểm tức thời ($t$).

## 2. Yêu Cầu Để Thực Hiện SLAM Đúng Nghĩa
Để xây dựng một bản đồ 2D hoàn chỉnh (`nav_msgs/msg/OccupancyGrid`) bằng các thuật toán như `slam_toolbox` hoặc `cartographer`, hệ thống bắt buộc phải có:
1. **Odometry (Ước lượng chuyển động)**:
   - Đo từ encoder bánh xe, IMU hoặc Visual Odometry.
   - Cung cấp biến đổi không gian `odom -> base_link`.
2. **Cây biến đổi không gian TF (Transform Tree)** đầy đủ:
   - `map -> odom -> base_link -> laser`.
3. **Cân chỉnh cơ khí (Extrinsics Calibration)**:
   - Tọa độ chính xác của cảm biến LiDAR so với tâm quay của robot ($x, y, z, roll, pitch, yaw$).

> [!WARNING]
> **Không tạo Odometry giả lập (Fake Odometry)** rồi tuyên bố đó là giải pháp SLAM hoàn chỉnh! Nếu không có encoder hoặc IMU thực tế, việc cố định robot đứng yên và chạy SLAM chỉ tạo ra bản đồ của một phòng đơn lẻ và sẽ sai lệch nghiêm trọng ngay khi robot di chuyển.

## 3. Nếu Muốn Mapping Không Cần Encoder (Laser Odometry Only)
Trong trường hợp robot chưa có encoder bánh xe, bạn có thể nghiên cứu các giải pháp **LiDAR-based SLAM** như:
- `slam_toolbox` ở chế độ **Async Scan Matcher** (tính toán odometry dựa trên việc so khớp liên tiếp các tia laser).
- Tuy nhiên, chế độ này yêu cầu CPU Raspberry Pi xử lý liên tục với tải tính toán cao hơn và dễ bị trượt (slip) nếu cảm biến xoay quá nhanh hoặc trong hành lang dài không có vật cản đặc trưng.

**Kết luận:** Hãy đảm bảo cảm biến C1 vượt qua bài test phần cứng trong dự án này trước khi tích hợp vào bất kỳ ngăn xếp SLAM hoặc Navigation (Nav2) nào.

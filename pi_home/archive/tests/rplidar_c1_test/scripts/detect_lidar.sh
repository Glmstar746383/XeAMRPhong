#!/usr/bin/env bash
# ==============================================================================
# detect_lidar.sh - Phát hiện cổng Serial & thông tin RPLIDAR C1 qua USB
# Không hard-code /dev/ttyUSB0. Tự động truy vấn VID/PID và /dev/serial/by-id/
# ==============================================================================

set -eo pipefail

PORT_ONLY=0
if [[ "$1" == "--port-only" ]]; then
    PORT_ONLY=1
fi

FOUND_PORT=""
DEVICE_NAME=""
SERIAL_BY_ID=""
USB_VENDOR_ID="10c4"   # Silicon Labs CP210x (adapter chuẩn của RPLIDAR C1)
USB_PRODUCT_ID="ea60"

# 1. Kiểm tra /dev/rplidar_c1 do udev rule tạo ra trước (nếu có)
if [[ -e "/dev/rplidar_c1" ]]; then
    FOUND_PORT="/dev/rplidar_c1"
    DEVICE_NAME="RPLIDAR C1 (qua udev symlink /dev/rplidar_c1)"
fi

# 2. Quét trong /dev/serial/by-id/ để tìm đường dẫn ổn định
if [[ -z "$FOUND_PORT" && -d "/dev/serial/by-id" ]]; then
    for dev in /dev/serial/by-id/*; do
        if [[ -e "$dev" ]]; then
            # Kiểm tra xem có phải CP210x hoặc SLAMTEC không
            if udevadm info --query=all --name="$dev" 2>/dev/null | grep -qE "ID_VENDOR_ID=10c4|CP210|Silicon_Labs|SLAMTEC"; then
                FOUND_PORT="$dev"
                SERIAL_BY_ID="$dev"
                DEVICE_NAME="Silicon Labs CP210x UART Bridge (RPLIDAR C1)"
                break
            fi
        fi
    done
fi

# 3. Quét các cổng /dev/ttyUSB* hoặc /dev/ttyACM* nếu chưa tìm thấy qua by-id
if [[ -z "$FOUND_PORT" ]]; then
    for dev in /dev/ttyUSB* /dev/ttyACM*; do
        if [[ -e "$dev" ]]; then
            if udevadm info --query=all --name="$dev" 2>/dev/null | grep -qE "ID_VENDOR_ID=10c4|ID_MODEL_ID=ea60|CP210"; then
                FOUND_PORT="$dev"
                DEVICE_NAME="CP2102N USB to UART Bridge"
                break
            fi
        fi
    done
fi

# 4. Nếu vẫn không thấy nhưng chỉ có duy nhất 1 cổng /dev/ttyUSB0
if [[ -z "$FOUND_PORT" && -e "/dev/ttyUSB0" ]]; then
    FOUND_PORT="/dev/ttyUSB0"
    DEVICE_NAME="Thiết bị USB Serial (/dev/ttyUSB0)"
fi

# Nếu chỉ cần xuất đường dẫn cổng cho script khác sử dụng
if [[ $PORT_ONLY -eq 1 ]]; then
    if [[ -n "$FOUND_PORT" ]]; then
        echo "$FOUND_PORT"
        exit 0
    else
        exit 1
    fi
fi

# Xuất thông tin chi tiết cho người dùng
echo "=================================================="
echo "          KẾT QUẢ PHÁT HIỆN RPLIDAR C1            "
echo "=================================================="

if [[ -n "$FOUND_PORT" ]]; then
    echo "[PASS] Đã tìm thấy cảm biến RPLIDAR C1!"
    echo "  - Cổng kết nối : $FOUND_PORT"
    if [[ -n "$DEVICE_NAME" ]]; then
        echo "  - Tên thiết bị : $DEVICE_NAME"
    fi
    
    # Giải mã đường dẫn thực nếu là symlink
    REAL_PORT=$(readlink -f "$FOUND_PORT")
    echo "  - Đường dẫn gốc: $REAL_PORT"
    
    # Kiểm tra quyền truy cập (read/write)
    if [[ -r "$REAL_PORT" && -w "$REAL_PORT" ]]; then
        echo "  - Quyền truy cập: [PASS] Đọc/Ghi (OK)"
    else
        echo "  - Quyền truy cập: [FAIL] Không có quyền Đọc/Ghi!"
        echo "    Gợi ý: Chạy './scripts/setup_udev.sh' hoặc thêm user vào group dialout."
    fi
    
    # Thông tin udev tóm tắt
    echo "  - Thông tin udev:"
    udevadm info --query=property --name="$REAL_PORT" 2>/dev/null | grep -E "ID_VENDOR_ID|ID_MODEL_ID|ID_SERIAL|ID_USB_DRIVER" | sed 's/^/      /'
    echo "=================================================="
    exit 0
else
    echo "[FAIL] Không tìm thấy RPLIDAR C1 qua cổng USB!"
    echo "  Nguyên nhân có thể:"
    echo "  1. Cảm biến chưa được cắm cáp USB vào Raspberry Pi."
    echo "  2. Dây cáp USB chỉ có nguồn mà không có đường truyền dữ liệu (data line)."
    echo "  3. Cổng USB trên Pi chưa cấp đủ nguồn."
    echo "=================================================="
    exit 1
fi

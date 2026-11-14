#!/usr/bin/env bash
# ==============================================================================
# setup_udev.sh - Cấu hình udev rule và quyền truy cập cổng Serial cho RPLIDAR C1
# Tạo symlink cố định /dev/rplidar_c1 và cấp quyền truy cập 0666 an toàn.
# ==============================================================================

set -eo pipefail

RULE_FILE="/etc/udev/rules.d/99-rplidar.rules"
BACKUP_DIR="/etc/udev/rules.d/backup"
CURRENT_USER=$(whoami)

echo "=================================================="
echo "      THIẾT LẬP QUYỀN VÀ UDEV RULE CHO RPLIDAR C1  "
echo "=================================================="

# 1. Thêm người dùng hiện tại vào nhóm dialout (nếu chưa có)
echo "[BƯỚC 1] Kiểm tra nhóm 'dialout' cho người dùng: $CURRENT_USER"
if groups "$CURRENT_USER" | grep -q "\bdialout\b"; then
    echo "  -> Người dùng '$CURRENT_USER' đã nằm trong nhóm 'dialout'. [PASS]"
else
    echo "  -> Đang thêm '$CURRENT_USER' vào nhóm 'dialout'..."
    sudo usermod -aG dialout "$CURRENT_USER"
    echo "  -> Đã thêm thành công. Lưu ý: Cần đăng xuất và đăng nhập lại để quyền có hiệu lực đầy đủ."
fi

# 2. Sao lưu rule cũ nếu đã tồn tại
if [[ -f "$RULE_FILE" ]]; then
    echo "[BƯỚC 2] Phát hiện file rule cũ. Đang sao lưu..."
    sudo mkdir -p "$BACKUP_DIR"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    sudo cp "$RULE_FILE" "$BACKUP_DIR/99-rplidar.rules.bak_$TIMESTAMP"
    echo "  -> Đã sao lưu tại $BACKUP_DIR/99-rplidar.rules.bak_$TIMESTAMP"
fi

# 3. Tạo rule udev mới cho Silicon Labs CP210x (VID: 10c4, PID: ea60)
# Thuộc tính:
# - ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60": Nhận diện chính xác chip USB adapter của C1.
# - MODE:="0666": Cho phép mọi ứng dụng của user đọc/ghi mà không cần sudo.
# - GROUP:="dialout": Đảm bảo thuộc sở hữu của nhóm giao tiếp nối tiếp.
# - SYMLINK+="rplidar_c1": Tạo liên kết tắt ổn định tại /dev/rplidar_c1.
echo "[BƯỚC 3] Tạo file udev rule tại $RULE_FILE..."
sudo bash -c "cat << 'EOF' > $RULE_FILE
# RPLIDAR C1 (CP2102N USB to UART Bridge)
KERNEL==\"ttyUSB*\", ATTRS{idVendor}==\"10c4\", ATTRS{idProduct}==\"ea60\", MODE:=\"0666\", GROUP:=\"dialout\", SYMLINK+=\"rplidar_c1\"
KERNEL==\"ttyACM*\", ATTRS{idVendor}==\"10c4\", ATTRS{idProduct}==\"ea60\", MODE:=\"0666\", GROUP:=\"dialout\", SYMLINK+=\"rplidar_c1\"
EOF"

echo "  -> Đã ghi rule thành công."

# 4. Kích hoạt và tải lại cấu hình udev
echo "[BƯỚC 4] Nạp lại cấu hình udev hệ thống..."
sudo udevadm control --reload-rules
sudo udevadm trigger
sleep 1

# 5. Kiểm tra kết quả
echo "[BƯỚC 5] Kiểm tra liên kết /dev/rplidar_c1..."
if [[ -e "/dev/rplidar_c1" ]]; then
    REAL_LINK=$(readlink -f /dev/rplidar_c1)
    PERMS=$(ls -l /dev/rplidar_c1)
    echo "  -> [PASS] Tạo symlink thành công: /dev/rplidar_c1 -> $REAL_LINK"
    echo "  -> Chi tiết quyền: $PERMS"
else
    echo "  -> [CHÚ Ý] Chưa thấy /dev/rplidar_c1 xuất hiện ngay lập tức."
    echo "     Nếu LiDAR đang cắm, hãy rút ra và cắm lại cáp USB để udev áp dụng ngay."
fi

echo "=================================================="
echo "          HOÀN TẤT CẤU HÌNH QUYỀN SERIAL          "
echo "=================================================="

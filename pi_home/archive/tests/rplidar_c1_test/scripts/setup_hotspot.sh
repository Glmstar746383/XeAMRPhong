#!/usr/bin/env bash
# ==============================================================================
# setup_hotspot.sh - Cấu hình Raspberry Pi tự phát Wi-Fi Hotspot cho Xe Tự Hành
# Tự động cấp IP tĩnh 10.42.0.1 cho Pi, không cần Router Wi-Fi, không cần dây
# ==============================================================================

set -e

HOTSPOT_SSID="${1:-XE_TU_HANH}"
HOTSPOT_PASS="${2:-12345678}"
IFNAME="wlan0"

echo "================================================================="
echo "   CẤU HÌNH RASPBERRY PI TỰ PHÁT SÓNG WI-FI HOTSPOT"
echo "================================================================="
echo " * Tên Wi-Fi (SSID) : $HOTSPOT_SSID"
echo " * Mật khẩu (PASS)  : $HOTSPOT_PASS (Tối thiểu 8 ký tự)"
echo " * Cổng mạng        : $IFNAME"
echo " * IP mặc định của xe: 10.42.0.1"
echo "================================================================="

# Kiểm tra quyền root / sudo
if [ "$EUID" -ne 0 ]; then
    echo "[LỖI] Vui lòng chạy lệnh với quyền sudo: sudo bash $0"
    exit 1
fi

# Kiểm tra NetworkManager (nmcli)
if ! command -v nmcli &> /dev/null; then
    echo "[!] Đang cài đặt NetworkManager..."
    apt-get update -y && apt-get install -y network-manager
fi

# Xóa cấu hình hotspot cũ nếu có
echo "-> Đang cấu hình điểm phát sóng mới..."
nmcli connection delete "AGV-Hotspot" 2>/dev/null || true

# Tạo kết nối Access Point (Hotspot) mới
nmcli connection add type wifi ifname "$IFNAME" con-name "AGV-Hotspot" autoconnect yes ssid "$HOTSPOT_SSID"
nmcli connection modify "AGV-Hotspot" 802-11-wireless.mode ap
nmcli connection modify "AGV-Hotspot" 802-11-wireless.band bg
nmcli connection modify "AGV-Hotspot" wifi-sec.key-mgmt wpa-psk
nmcli connection modify "AGV-Hotspot" wifi-sec.psk "$HOTSPOT_PASS"
nmcli connection modify "AGV-Hotspot" ipv4.method shared
nmcli connection modify "AGV-Hotspot" ipv4.addresses 10.42.0.1/24

# Khởi động Hotspot ngay lập tức
echo "-> Đang kích hoạt phát sóng Wi-Fi..."
nmcli connection up "AGV-Hotspot"

echo ""
echo "================================================================="
echo " ✅ HOÀN TẤT! RASPBERRY PI ĐANG PHÁT SÓNG WI-FI:"
echo "================================================================="
echo " 📶 Tên Wi-Fi : $HOTSPOT_SSID"
echo " 🔑 Mật khẩu  : $HOTSPOT_PASS"
echo " 🌐 Địa chỉ IP : 10.42.0.1"
echo "-----------------------------------------------------------------"
echo " CÁCH KẾT NỐI TỪ MÁY TÍNH & ĐIỆN THOẠI:"
echo " 1. Trên Laptop/Desktop & Điện thoại: Bắt vào Wi-Fi '$HOTSPOT_SSID'"
echo " 2. Nhập mật khẩu: '$HOTSPOT_PASS'"
echo " 3. Mở trình duyệt truy cập: http://10.42.0.1:8080/"
echo "================================================================="

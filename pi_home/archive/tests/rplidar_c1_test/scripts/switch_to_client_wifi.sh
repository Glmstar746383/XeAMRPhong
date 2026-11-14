#!/usr/bin/env bash
# ==============================================================================
# switch_to_client_wifi.sh - Chuyển Raspberry Pi về lại chế độ bắt Wi-Fi gia đình
# ==============================================================================

if [ "$EUID" -ne 0 ]; then
    echo "[LỖI] Vui lòng chạy lệnh với quyền sudo: sudo bash $0 <Ten_Wifi> <Mat_Khau>"
    exit 1
fi

WIFI_NAME="$1"
WIFI_PASS="$2"

# Tắt Hotspot
echo "-> Đang tắt điểm phát Wi-Fi Hotspot..."
nmcli connection down "AGV-Hotspot" 2>/dev/null || true

if [ -n "$WIFI_NAME" ] && [ -n "$WIFI_PASS" ]; then
    echo "-> Đang kết nối vào Wi-Fi: $WIFI_NAME..."
    nmcli device wifi connect "$WIFI_NAME" password "$WIFI_PASS"
fi

echo "✅ Đã chuyển về chế độ Client Wi-Fi bình thường."

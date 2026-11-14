#!/usr/bin/env bash
# ==============================================================================
# connect_wifi_minhkhang.sh - Kết nối Raspberry Pi vào mạng Wi-Fi 'minhkhang'
# ==============================================================================

WIFI_SSID="minhkhang"
WIFI_PASS="Minhkhang2005"

echo "================================================================="
echo "   ĐANG KẾT NỐI RASPBERRY PI VÀO WI-FI: $WIFI_SSID"
echo "================================================================="

if [ "$EUID" -ne 0 ]; then
    echo "[LỖI] Vui lòng chạy lệnh với quyền sudo: sudo bash $0"
    exit 1
fi

# Tắt Hotspot nếu đang bật
nmcli connection down "AGV-Hotspot" 2>/dev/null || true

# Quét và kết nối Wi-Fi minhkhang
echo "-> Đang kết nối vào Wi-Fi $WIFI_SSID..."
nmcli device wifi rescan 2>/dev/null || true
sleep 1

if nmcli device wifi connect "$WIFI_SSID" password "$WIFI_PASS"; then
    echo ""
    echo "================================================================="
    echo " ✅ ĐÃ KẾT NỐI THÀNH CÔNG VÀO WI-FI '$WIFI_SSID'!"
    echo "================================================================="
    
    # Lấy địa chỉ IP Wi-Fi được cấp
    IP_ADDR=$(hostname -I | awk '{print $1}')
    
    echo " 🌐 Địa chỉ IP của Pi   : $IP_ADDR"
    echo " 🏷️ Tên miền nội bộ mDNS: http://khang.local:8080/"
    echo "-----------------------------------------------------------------"
    echo " TRÊN MÁY TÍNH DESKTOP & ĐIỆN THOẠI (Bắt cùng Wi-Fi minhkhang):"
    echo " 1. Mở trình duyệt Desktop : http://$IP_ADDR:8080/ hoặc http://khang.local:8080/"
    echo " 2. Mở WebViewer trên App  : http://$IP_ADDR:8080/radar"
    echo " 3. API cho Block MIT App  : http://$IP_ADDR:8080/api/zones"
    echo "================================================================="
else
    echo "[!] Kết nối thất bại. Vui lòng kiểm tra lại khoảng cách đến Router hoặc trạng thái phát sóng."
fi

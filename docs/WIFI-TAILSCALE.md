# Äá»”I WI-FI Táº I CHá»– Má»šI â€” Lá»†NH `wifi`

Cáº­p nháº­t: 2026-11-17 Â· Ãp dá»¥ng trÃªn Pi (Ubuntu 24.04, netplan + systemd-networkd)

Má»¥c tiÃªu: Ä‘áº¿n Ä‘á»‹a Ä‘iá»ƒm má»›i **khÃ´ng cáº§n sá»­a netplan báº±ng tay**. Cáº¯m LAN (hoáº·c vÃ o
báº±ng Tailscale) â†’ SSH â†’ gÃµ `wifi` â†’ chá»n máº¡ng â†’ nháº­p máº­t kháº©u â†’ xong.

---

## 1. Quy trÃ¬nh 3 bÆ°á»›c

```powershell
# 1. Cáº¯m dÃ¢y LAN vÃ o xe (hoáº·c vÃ o báº±ng Tailscale náº¿u Ä‘Ã£ cÃ³ máº¡ng)
ssh khangho@192.168.1.14          # hoáº·c ssh khangho@100.118.177.83

# 2. TrÃªn xe:
wifi

# 3. LÃ m theo menu:
#    Wi-Fi tháº¥y Ä‘Æ°á»£c (máº¡nh â†’ yáº¿u):
#      1. â–ˆâ–ˆâ–ˆâ–ˆ Phong Nguyen     -51 dBm  WPA2
#      2. â–ˆâ–ˆâ–ˆ  Lan Phuong       -57 dBm  WPA2
#      0. Nháº­p tÃªn Wi-Fi khÃ¡c (máº¡ng áº©n)
#    Chá»n sá»‘ hoáº·c gÃµ tÃªn Wi-Fi: 1
#    Máº­t kháº©u Wi-Fi cá»§a 'Phong Nguyen': ********
#    Tiáº¿p tá»¥c? [y/N] y
```

Káº¿t quáº£:

```
âœ… ÄÃƒ Káº¾T Ná»I: Phong Nguyen
  Wi-Fi     : Phong Nguyen  (-51 dBm)
  IPv4      : 192.168.1.14/24
  Internet  : OK
  Tailscale : Ä‘ang cháº¡y  100.118.177.83
Gá»£i Ã½:
  â€¢ RÃºt dÃ¢y LAN Ä‘Æ°á»£c; xe tá»± vÃ o láº¡i máº¡ng nÃ y khi khá»Ÿi Ä‘á»™ng.
  â€¢ SSH ná»™i bá»™     : ssh khangho@192.168.1.14
  â€¢ SSH Tailscale  : ssh khangho@100.118.177.83
```

---

## 2. CÃ¡c lá»‡nh

| Lá»‡nh | Viá»‡c |
|---|---|
| `wifi` | quÃ©t + chá»n máº¡ng + nháº­p máº­t kháº©u + káº¿t ná»‘i |
| `wifi list` | chá»‰ liá»‡t kÃª máº¡ng Ä‘ang tháº¥y (kÃ¨m cÆ°á»ng Ä‘á»™, WPA2/WPA3/Má»ž) |
| `wifi status` | Wi-Fi hiá»‡n táº¡i, IP, gateway, Internet, Tailscale, cÃ¡c máº¡ng Ä‘Ã£ lÆ°u |
| `wifi -y` | bá» bÆ°á»›c há»i xÃ¡c nháº­n |
| `wifi --ssid "ABC" --password "..."` | khÃ´ng tÆ°Æ¡ng tÃ¡c (máº­t kháº©u lá»™ trong `ps` â€” háº¡n cháº¿ dÃ¹ng) |
| `wifi --ssid "ABC" --password-file /root/pw` | khÃ´ng tÆ°Æ¡ng tÃ¡c, máº­t kháº©u Ä‘á»c tá»« file |
| `wifi --dry-run --ssid "ABC" --password "..."` | chá»‰ in YAML + kiá»ƒm tra cÃº phÃ¡p, **khÃ´ng Ã¡p dá»¥ng** |
| `wifi --ssid "ABC" --no-apply` | chá»‰ ghi cáº¥u hÃ¬nh, chÆ°a Ã¡p dá»¥ng |

`wifi` tá»± `sudo` (khÃ´ng cáº§n gÃµ `sudo wifi`).

---

## 3. NÃ³ lÃ m gÃ¬ bÃªn trong

1. QuÃ©t báº±ng `iw dev wlan0 scan`, gá»™p theo SSID, sáº¯p xáº¿p theo cÆ°á»ng Ä‘á»™.
2. Ghi `/etc/netplan/70-wifi-user.yaml` (quyá»n `600`) â€” **chá»‰ file nÃ y**, khÃ´ng sá»­a
   `50-cloud-init.yaml` / `60-wifi.yaml`.
3. `netplan generate` (kiá»ƒm tra cÃº phÃ¡p) â†’ `netplan apply`.
4. Ã‰p `wpa_supplicant` chá»n Ä‘Ãºng SSID vá»«a nháº­p (`wpa_cli select_network`).
5. Chá» tá»‘i Ä‘a **45 s** cho tá»›i khi cÃ³ SSID + IPv4.
6. Táº¯t power-save Wi-Fi (`wifi-powersave-off.service`, báº­t 1 láº§n, cháº¡y má»—i boot).
7. In IP + gá»£i Ã½ `ssh khangho@<ip>` vÃ  `ssh khangho@<tailscale-ip>`.

**An toÃ n:** trÆ°á»›c khi Ã¡p dá»¥ng, toÃ n bá»™ `/etc/netplan` Ä‘Æ°á»£c sao lÆ°u vÃ o
`/root/netplan-backup-<thá»i gian>`. Náº¿u khÃ´ng káº¿t ná»‘i Ä‘Æ°á»£c trong 45 s, script tá»±
khÃ´i phá»¥c báº£n sao lÆ°u vÃ  `netplan apply` láº¡i â†’ Wi-Fi cÅ© trá»Ÿ láº¡i. Náº¿u máº¡ng lÃ  WPA3,
script tá»± thá»­ láº¡i vá»›i `key-management: sae`.

> LÆ°u Ã½: náº¿u báº¡n Ä‘ang SSH **qua Wi-Fi**, lÃºc `netplan apply` phiÃªn sáº½ ngáº¯t vÃ i giÃ¢y.
> NÃªn cáº¯m LAN hoáº·c dÃ¹ng Tailscale khi Ä‘á»•i máº¡ng. Script cÃ³ há»i xÃ¡c nháº­n trÆ°á»›c khi lÃ m
> (bá» qua báº±ng `-y`).

---

## 4. Máº¡ng LAN (eth0)

- `61-eth0-dhcp.yaml` báº­t **DHCP cho eth0** (cáº¯m dÃ¢y vÃ o router lÃ  cÃ³ IP ngay),
  Ä‘á»“ng thá»i váº«n giá»¯ Ä‘á»‹a chá»‰ tÄ©nh `192.168.1.4/24` khai bÃ¡o trong `50-cloud-init.yaml`
  Ä‘á»ƒ cáº¯m trá»±c tiáº¿p laptop váº«n vÃ o Ä‘Æ°á»£c.
- IPv6 link-local luÃ´n cÃ³ (dÃ¹ng cho cáº¯m trá»±c tiáº¿p: `fe80::...%eth0`).
- Kiá»ƒm tra: `ip -br addr show eth0`.

---

## 5. Tailscale (khi nÆ¡i má»›i cháº·n port)

- `tailscaled` cháº¡y tá»± Ä‘á»™ng; Ä‘á»•i Wi-Fi xong Tailscale tá»± káº¿t ná»‘i láº¡i.
- IP hiá»‡n táº¡i: `100.118.177.83` â†’ `ssh khangho@100.118.177.83` tá»« báº¥t ká»³ Ä‘Ã¢u.
- Kiá»ƒm tra: `wifi status` hoáº·c `tailscale status`, `tailscale ip -4`.
- Náº¿u chÆ°a Ä‘Äƒng nháº­p: `sudo tailscale up --ssh` (má»Ÿ link xÃ¡c thá»±c).

---

## 6. Máº¹o chá»‘ng "máº¥t liÃªn láº¡c" khi Ä‘i xa

1. **LuÃ´n giá»¯ 1 hotspot Ä‘iá»‡n thoáº¡i Ä‘Ã£ lÆ°u** trÃªn xe (vÃ­ dá»¥ tÃªn `AGV-hotspot`).
   TrÆ°á»›c khi Ä‘i, thÃªm 1 láº§n báº±ng `wifi`; khi Ä‘áº¿n nÆ¡i khÃ´ng cÃ³ LAN/Tailscale, báº­t
   hotspot Ä‘Ã³ â†’ xe tá»± vÃ o â†’ SSH â†’ `wifi` Ä‘á»ƒ Ä‘á»•i sang máº¡ng cá»§a khÃ¡ch.
2. TrÆ°á»›c khi Ä‘á»•i máº¡ng, má»Ÿ sáºµn 2 cá»­a sá»• SSH: má»™t qua LAN/Tailscale, má»™t qua Wi-Fi.
3. Náº¿u Ä‘á»•i máº¡ng tháº¥t báº¡i, chá» ~60 s Ä‘á»ƒ script tá»± khÃ´i phá»¥c; khÃ´ng rÃºt Ä‘iá»‡n.
4. Sau khi vÃ o máº¡ng má»›i, cháº¡y `wifi status` Ä‘á»ƒ xÃ¡c nháº­n Internet + Tailscale.

---

## 7. Sá»± cá»‘

| Hiá»‡n tÆ°á»£ng | CÃ¡ch xá»­ lÃ½ |
|---|---|
| `wifi: command not found` | cÃ i láº¡i: `sudo install -m 755 ~/agv/tools/wifi /usr/local/bin/wifi` |
| KhÃ´ng quÃ©t tháº¥y máº¡ng | `sudo iw dev wlan0 scan` xem lá»—i; kiá»ƒm tra `rfkill list` (unblock) |
| Sai máº­t kháº©u | script tá»± khÃ´i phá»¥c máº¡ng cÅ©; cháº¡y láº¡i `wifi` vÃ  nháº­p Ä‘Ãºng |
| Káº¿t ná»‘i nhÆ°ng khÃ´ng cÃ³ Internet | router cháº·n/portal Ä‘Äƒng nháº­p; thá»­ `ping 1.1.1.1`, Ä‘á»•i DNS `resolvectl` |
| Muá»‘n quay láº¡i máº¡ng cÅ© | `wifi` chá»n láº¡i máº¡ng cÅ© (Ä‘Ã£ lÆ°u trong netplan) |
| Netplan há»ng | khÃ´i phá»¥c: `sudo rm -rf /etc/netplan && sudo cp -a /root/netplan-backup-<ts> /etc/netplan && sudo netplan apply` |
| Wi-Fi cháº­p chá»n | kiá»ƒm tra `iw dev wlan0 get power_save` pháº£i lÃ  `off`; xem `systemctl status wifi-powersave-off` |

---

## 8. File liÃªn quan

| File | Vai trÃ² |
|---|---|
| `/usr/local/bin/wifi` | cÃ´ng cá»¥ (báº£n gá»‘c trong repo: `v2/agv/tools/wifi`) |
| `/etc/netplan/70-wifi-user.yaml` | máº¡ng do `wifi` thÃªm (tá»± sinh) |
| `/etc/netplan/61-eth0-dhcp.yaml` | DHCP cho eth0 |
| `/etc/systemd/system/wifi-powersave-off.service` | táº¯t power-save Wi-Fi |
| `/root/netplan-backup-*` | báº£n sao lÆ°u trÆ°á»›c má»—i láº§n Ä‘á»•i máº¡ng |

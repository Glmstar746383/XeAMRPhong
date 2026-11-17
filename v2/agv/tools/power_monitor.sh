#!/bin/bash
# Ghi lai dien ap / nhiet do / wifi moi 10 giay de chan doan mat dien.
LOG=/home/khangho/logs/power_monitor.log
mkdir -p /home/khangho/logs
echo "$(date '+%F %T') === BOOT $(cat /proc/sys/kernel/random/boot_id) ===" >> "$LOG"

while true; do
  ts=$(date '+%F %T')
  temp=$(vcgencmd measure_temp 2>/dev/null | cut -d= -f2)
  thr=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
  up=$(cut -d. -f1 /proc/uptime)
  sig=$(awk 'NR==3{print $3}' /proc/net/wireless 2>/dev/null)
  ssid=$(nmcli -t -f ACTIVE,SSID dev wifi 2>/dev/null | awk -F: '$1=="yes"{print $2; exit}')
  echo "$ts up=${up}s temp=${temp:-?} throttled=${thr:-?} wifi=${sig:-none} ssid=${ssid:-?}" >> "$LOG"
  n=$(wc -l < "$LOG" 2>/dev/null || echo 0)
  if [ "$n" -gt 3000 ]; then tail -n 2000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"; fi
  sleep 10
done


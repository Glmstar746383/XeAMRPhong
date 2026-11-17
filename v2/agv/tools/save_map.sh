#!/usr/bin/env bash
# Lưu bản đồ SLAM đang chạy trên xe ra ~/agv/maps/
#
#   bash ~/agv/tools/save_map.sh            # tên tự động: map_YYYYmmdd_HHMMSS
#   bash ~/agv/tools/save_map.sh nha_tang1  # đặt tên riêng
#
# Sinh ra 3 file:
#   <ten>.pgm + <ten>.yaml   -> bản đồ chuẩn ROS (dùng cho nav2 map_server / xem lại)
#   <ten>.posegraph          -> đồ thị SLAM (dùng cho slam_toolbox deserialize / localization)
# và các symlink latest.* trỏ về bản mới nhất.

set -eo pipefail

MAP_DIR="${MAP_DIR:-$HOME/agv/maps}"
SKIP_STOP="${SKIP_STOP:-0}"
NAME="${1:-map_$(date +%Y%m%d_%H%M%S)}"
TARGET="$MAP_DIR/$NAME"

# Phải source ROS trước khi bật `set -u`: setup.bash dùng biến chưa khai báo.
source /opt/ros/jazzy/setup.bash >/dev/null 2>&1 || true
set -u

die() { echo "LỖI: $*" >&2; exit 1; }

mkdir -p "$MAP_DIR"

# SLAM đang chạy mới có map để lưu
pgrep -f '^/opt/ros/jazzy/lib/slam_toolbox/async_slam_toolbox_node( |$)' >/dev/null \
  || die "slam_toolbox không chạy (systemctl status agv)"

if [ "$SKIP_STOP" != "1" ]; then
  # Dừng xe trước khi chốt map để ảnh quét không bị nhoè giữa hai thời điểm
  curl -s -m 3 "http://127.0.0.1:8080/api/cmd?val=STOP" >/dev/null 2>&1 || true
  sleep 2
fi

# slam_toolbox thỉnh thoảng trả 255 (ghi file lỗi) một lần rồi lần sau OK,
# nên thử lại 3 lần trước khi báo hỏng.
try_call() { # $1=service $2=type $3=request  -> in ra output, trả 0 nếu result=0
  local out rc=1
  for _ in 1 2 3; do
    out=$(timeout 30 ros2 service call "$1" "$2" "$3" 2>&1) || out=""
    case "$out" in *result=0*) return 0 ;; esac
    sleep 1
  done
  printf '%s' "$out"
  return "$rc"
}

OUT=$(try_call /slam_toolbox/save_map slam_toolbox/srv/SaveMap \
        "{name: {data: '$TARGET'}}") \
  || die "save_map thất bại 3 lần: $OUT"

OUT2=$(try_call /slam_toolbox/serialize_map slam_toolbox/srv/SerializePoseGraph \
         "{filename: '$TARGET'}") \
  || die "serialize_map thất bại 3 lần: $OUT2"

[ -s "$TARGET.pgm" ] || die "không thấy $TARGET.pgm"
[ -s "$TARGET.yaml" ] || die "không thấy $TARGET.yaml"

ln -sfn "$NAME.pgm" "$MAP_DIR/latest.pgm"
ln -sfn "$NAME.yaml" "$MAP_DIR/latest.yaml"
ln -sfn "$NAME.posegraph" "$MAP_DIR/latest.posegraph"

echo
echo "ĐÃ LƯU BẢN ĐỒ"
echo "  thư mục : $MAP_DIR"
echo "  tên     : $NAME"
ls -lh "$TARGET".* | awk '{printf "  %-10s %s\n", $5, $9}'

python3 - "$TARGET" <<'PY' || true
import re, sys
base = sys.argv[1]
with open(base + '.pgm', 'rb') as f:
    tokens = []
    while len(tokens) < 4:
        line = f.readline()
        if not line:
            break
        tokens += line.split(b'#')[0].split()
w, h = int(tokens[1]), int(tokens[2])
txt = open(base + '.yaml', encoding='utf-8', errors='replace').read()
res = re.search(r'resolution:\s*([0-9.]+)', txt)
org = re.search(r'origin:\s*\[([^\]]+)\]', txt)
print('  kích thước: %d x %d ô  (%.2f m x %.2f m)' % (w, h, w * float(res.group(1)), h * float(res.group(1))))
print('  độ phân giải: %s m/ô' % (res.group(1) if res else '?'))
print('  gốc toạ độ : [%s]' % (org.group(1).strip() if org else '?'))
PY

echo
echo "Dùng lại về sau: xem ~/docs/LUU-MAP-THU-CONG.md"

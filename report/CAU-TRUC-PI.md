# Cau truc Pi - AGV (cap nhat 2026-11-13)

## Thu muc chinh

| Duong dan | Noi dung | Ghi chu |
|---|---|---|
| `~/agv/` | App dang chay: brain, session, navigation, web UI, models | git repo, baseline 64dd836 |
| `~/agv-cam/` | Module camera: stream MJPEG, range node, calib | git repo, baseline d6d5b94 |
| `~/rplidar_c1_ws/` | ROS 2 workspace cho RPLiDAR C1 | duoc `source` khi khoi dong - KHONG DI CHUYEN |
| `~/slam_calibration_tools/` | `slam_tuned.yaml` | start script doc path nay - KHONG DI CHUYEN |
| `~/archive/snapshots/` | 36 ban snapshot app cu (agv_*) | chi de tham khao |
| `~/archive/scripts/` | 115 script sua mot lan (fix_*, apply_*, unblock_*) | chi de tham khao |
| `~/archive/evidence/` | 4 thu muc evidence_* | log/anh bang chung cu |
| `~/archive/app_baks/` | Toan bo file .bak cua code | 28+ file, khong con trong app |
| `~/archive/pkg/` | deb cache, goi cai dat | |
| `~/archive/tests/` | rplidar_c1_test, robot_ws (rong) | |
| `~/firmware/` | firmware.bin, merged_145.bin, bootloader, partitions + 3 ban cu | |
| `~/logs/legacy/` | log cu (robot-setup-*, start_agv.log...) | |
| `~/docs/` | tai lieu nay + `private/agv_gateway_credentials.txt` | |

## Service dang chay

| Service | Cong | WorkingDirectory |
|---|---|---|
| `agv.service` | 8080 | `~/agv` |
| `agv-cam.service` | 8081 | `~/agv-cam/app` |
| `agv-gateway.service` | 8090 | `/opt/agv-gateway` |
| `agv-cam-range.service` | topic ROS 2 | `~/agv-cam/nodes` |

Lenh: `sudo systemctl restart agv agv-cam` (phai dung `sudo`, user thuong khong duoc phep).

## Symlink tuong thich - KHONG XOA

```
~/agv_codex_reader_20261003_0652 -> ~/agv
~/agv_cam_20261027               -> ~/agv-cam/app
~/camera_calib.json              -> ~/agv-cam/calib/camera_calib.json
~/floor_ref.jpg                  -> ~/agv-cam/calib/floor_ref.jpg
```

Ly do: code va service cu dung cac path nay. Symlink giu cho chung chay ma
khong phai sua code.

## Git

- `~/agv`: baseline "trang thai dang chay 2026-11-13". Khong chua `.bak`,
  `runtime/`, `logs/`, `ai_local_planner/exported|checkpoints`.
- `~/agv-cam`: baseline camera WIP.
- Chua co remote. Muon day len GitHub:
  `git remote add origin <url> && git push -u origin master`

## Camera - trang thai hien tai

Da co:
- `~/agv-cam/app/cam_stream.py` - MJPEG server :8081, da chay on dinh
- `~/agv-cam/nodes/cam_range_node.py` - node ROS 2, phat `/cam_range`, `/cam_obstacle`
- `~/agv-cam/nodes/cam_calib_server.py` - web hieu chuan, xuat `camera_calib.json`
- `~/agv-cam/calib/camera_calib.json` - hieu chuan hien tai (pinhole_ground, A=54.88, v0=177.81, rms=1.56cm)

### Da chay tu dong (2026-11-13)

`agv-cam-range.service` -> enabled, active, phat `/cam_range` va `/cam_obstacle` @ 10 Hz.

Thong so hieu chuan dang dung:
```
A = 54.9   v0 = 177.8   cx = 320.2   fx = 457.4 (voi camera cao 0.12 m)
rms = 0.016 m   dai hop le 0.20 - 1.00 m
```

Lenh quan ly:
```bash
sudo systemctl status agv-cam-range
sudo systemctl restart agv-cam-range
ros2 topic echo /cam_range --once
ros2 topic echo /cam_obstacle --once
journalctl -u agv-cam-range -n 50
```

### Ket qua kiem chung dau tien (13/11)

Camera phat hien soi day dien den tren san cach 18 cm -> `/cam_range = 0.183`.
LiDAR cung thoi diem chi thay vat gan nhat o 1.006 m (vi tia quet nam tren
mat san, khong thay vat thap). => Camera bu dung diem mu cua LiDAR.

### Chua noi vao brain

`agv_unified_brain.py` moi subscribe `/scan` va `/map`.

Buoc tiep theo:
1. [x] `agv-cam-range.service` chay node tu dong
2. [ ] Doi chieu sai so camera vs LiDAR tren vat chuan (hop 30-50 cm)
3. [ ] Brain subscribe `/cam_obstacle`, dung nhu lop chan phu:
       - chi tin khi `d < 0.35 m`
       - do lech ngang trong hanh lang than xe
       - timeout 2 s: mat tin hieu thi bo qua, LiDAR van la nguon chinh

### Luu y ky thuat

- `--cam-height` la chieu cao camera so voi san (m). Chi anh huong den
  lech ngang X, KHONG anh huong khoang cach d. Do lai bang thuoc neu thay doi.
- Anh nen `floor_ref.jpg` phai chup dung goc camera hien tai. Neu doi goc
  camera thi phai hieu chuan lai bang `cam_calib_server.py`.
- Node chiu duoc mat frame (tra 9.9 = duong trong) va tu restart sau 3 s.

## Rollback

Backup toan bo home truoc khi don:
`/tmp/agv_home_backup_20261111_1931.tar.gz` (81 MB)
Ban copy tren Windows: `E:\xetuhanhchuanhoakhoangcach\_backup\`
Khoi phuc: `tar xzf <file> -C /home/khangho`

Unit file cu: `/etc/systemd/system/agv.service.bak_20261113`,
`/etc/systemd/system/agv-cam.service.bak_20261113`

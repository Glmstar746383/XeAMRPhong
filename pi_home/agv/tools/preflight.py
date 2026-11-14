#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preflight kiem tra toan bo he thong AGV truoc khi cho xe chay.

Chay:  python3 ~/agv/tools/preflight.py
Khong dieu khien gi, chi doc trang thai. An toan tuyet doi.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

OK, WARN, FAIL = "\033[92mPASS\033[0m", "\033[93mWARN\033[0m", "\033[91mFAIL\033[0m"
rows = []


def add(name, level, detail=""):
    rows.append((name, level, detail))


def http(path, timeout=3):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080" + path, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"__error__": str(e)}


def check_services():
    for svc in ("agv", "agv-cam", "agv-cam-range", "agv-gateway"):
        p = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True)
        st = p.stdout.strip()
        add("service " + svc, OK if st == "active" else FAIL, st)


def check_http():
    for name, port, path in (("brain", 8080, "/"), ("camera", 8081, "/health"),
                             ("gateway", 8090, "/")):
        code = "?"
        try:
            req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path))
            with urllib.request.urlopen(req, timeout=3) as r:
                code = r.status
        except urllib.error.HTTPError as e:
            code = e.code
        except Exception as e:
            code = str(e)[:40]
        good = code in (200, 401)
        add("http %s :%d" % (name, port), OK if good else FAIL, str(code))


def check_telemetry():
    t = http("/api/telemetry")
    if "__error__" in t:
        add("telemetry", FAIL, t["__error__"])
        return {}
    c = t.get("control", {})
    lidar = t.get("lidar", {})

    add("lidar ket noi", OK if lidar.get("connected") else FAIL,
        "age=%.3fs points=%s" % (lidar.get("age_s", -1), lidar.get("points")))
    min_m = t.get("min_m")
    if min_m is None:
        add("vung truoc trong", WARN, "khong co min_m")
    elif min_m < 0.25:
        add("vung truoc trong", WARN, "vat can %.2f m" % min_m)
    else:
        add("vung truoc trong", OK, "gan nhat %.2f m" % min_m)

    d0_age = c.get("d0_age_s")
    if d0_age is None:
        add("telemetry MCU (d0)", FAIL, "chua co")
    elif d0_age <= 0.30:
        add("telemetry MCU (d0)", OK, "%.2fs" % d0_age)
    else:
        add("telemetry MCU (d0)", FAIL, "cu %.2fs (MCU khong tra loi)" % d0_age)

    safety = (c.get("latest_d0") or {}).get("safety")
    add("safety MCU", OK if safety == "DISARMED" else WARN, str(safety))

    fault = c.get("fault")
    add("fault", FAIL if fault else OK, str(fault))
    latched = c.get("latched")
    add("latched", WARN if latched else OK,
        "%s (binh thuong khi chua ARM)" % latched if latched else str(latched))
    add("armed", OK if c.get("armed") else WARN, str(c.get("armed")))
    add("preflight_ready", OK if c.get("preflight_ready") else FAIL,
        str(c.get("preflight_ready")))
    add("auto_mode", WARN if t.get("auto") else OK, str(t.get("auto")))
    return t


def check_topics():
    env = dict(os.environ, ROS_DOMAIN_ID="0")
    cli = ("source /opt/ros/jazzy/setup.bash >/dev/null 2>&1; timeout 12 ros2 topic list")
    p = subprocess.run(["bash", "-lc", cli], capture_output=True, text=True, env=env)
    topics = set(p.stdout.split())
    for name in ("/scan", "/map", "/cam_range"):
        add("topic " + name, OK if name in topics else FAIL, "")
    # tan so /scan
    p = subprocess.run(
        ["bash", "-lc",
         "source /opt/ros/jazzy/setup.bash >/dev/null 2>&1; "
         "timeout 9 ros2 topic hz /scan --window 20"],
        capture_output=True, text=True, env=env)
    line = [l for l in p.stdout.splitlines() if "average rate" in l]
    if line:
        hz = float(line[-1].split("average rate:")[1].split()[0])
        add("/scan tan so", OK if hz > 5 else WARN, "%.1f Hz" % hz)
    else:
        add("/scan tan so", FAIL, "khong doc duoc")


def check_tf():
    cli = ("source /opt/ros/jazzy/setup.bash >/dev/null 2>&1; "
           "timeout 8 ros2 run tf2_ros tf2_echo map base_footprint 2>&1 | head -12")
    p = subprocess.run(["bash", "-lc", cli], capture_output=True, text=True,
                       env=dict(os.environ, ROS_DOMAIN_ID="0"))
    ok = "Translation" in p.stdout
    add("TF map->base_footprint", OK if ok else FAIL,
        "co" if ok else "chua co (chua SLAM xong)")


def check_cam_range():
    cli = ("source /opt/ros/jazzy/setup.bash >/dev/null 2>&1; "
           "timeout 8 ros2 topic echo /cam_range --once 2>/dev/null | head -1")
    p = subprocess.run(["bash", "-lc", cli], capture_output=True, text=True,
                       env=dict(os.environ, ROS_DOMAIN_ID="0"))
    if "data" in p.stdout:
        add("/cam_range", OK, p.stdout.strip()[:40])
    else:
        add("/cam_range", WARN, "khong co mau")


def main():
    print("=" * 62)
    print(" PREFLIGHT AGV  %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 62)
    check_services()
    check_http()
    t = check_telemetry()
    if t:
        check_cam_range()
        check_topics()
        check_tf()

    for name, level, detail in rows:
        print("  %-26s %s  %s" % (name, level, detail))

    fails = sum(1 for _, l, _ in rows if l == FAIL)
    warns = sum(1 for _, l, _ in rows if l == WARN)
    print("-" * 62)
    if fails:
        print("  KET LUAN: %d FAIL / %d WARN -> CHUA CHAY DUOC" % (fails, warns))
    elif warns:
        print("  KET LUAN: 0 FAIL / %d WARN -> chay duoc, kiem tra muc WARN" % warns)
    else:
        print("  KET LUAN: SAN SANG")
    print("=" * 62)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

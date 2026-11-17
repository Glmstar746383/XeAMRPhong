#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Node ROS 2: do khoang cach vat can tu camera da hieu chuan.

Phat:
  /cam_range     sensor_msgs/Float32         khoang cach (m); 9.9 = duong trong
  /cam_obstacle  geometry_msgs/PointStamped  x = lech ngang (m), y = khoang cach (m),
                                             z = do rong cum (pixel)
  /cam_bg_diff   sensor_msgs/Float32         do lech trung binh so voi nen (0..255)
  /cam_bg_frac   sensor_msgs/Float32         ti le cot ROI khac nen (0..1)

Chay:
  python3 cam_range_node.py \
      --calib ~/camera_calib.json \
      --bg ~/floor_ref.jpg \
      --cam-height 0.12 \
      --source http://127.0.0.1:8081/snapshot.jpg

V2.1: phat hien theo CUM 2D (connected components) thay vi tung cot:
  - loai cum cham mep ROI
  - yeu cau kich thuoc toi thieu (min-w/min-h/min-area) -> khong bat vach gach
  - kiem tra mau (V/S) de loai phan chieu tren san bong
  - giu diem tiep xuc = day cum; lech ngang = tam cum
"""
import argparse
import json
import os
import sys
import time
import urllib.request

import cv2
import numpy as np

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.executors import ExternalShutdownException
    from std_msgs.msg import Float32, Empty
    from geometry_msgs.msg import PointStamped
    HAVE_ROS = True
except Exception:
    HAVE_ROS = False


CLEAR_VALUE = 9.9


class RangeModel:
    def __init__(self, path, cam_height=None):
        with open(path, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        m = d.get("range_model")
        if not m:
            raise RuntimeError("file calib chua co range_model - hay hieu chuan truoc")
        self.A = float(m["A"])
        self.v0 = float(m["v0"])
        self.rms = float(m.get("rms", 0.0))
        lo_hi = m.get("valid_range_m") or [0.3, 3.0]
        self.lo, self.hi = float(lo_hi[0]), float(lo_hi[1])

        samples = d.get("samples") or []
        self.cx = (float(np.mean([s["u"] for s in samples])) if samples
                   else float(d.get("image_size", [640, 480])[0]) / 2.0)

        h = cam_height if cam_height else float(d.get("cam_height_m") or 0)
        self.fx = (self.A / h) if h > 1e-6 else 0.0

    def distance(self, v_px):
        den = v_px - self.v0
        if den <= 0.5:
            return None
        return self.A / den

    def lateral(self, u_px, d):
        if self.fx <= 1e-6 or d is None:
            return 0.0
        return (u_px - self.cx) * d / self.fx


class FrameGrabber:
    def __init__(self, source):
        self.source = source
        self.cap = None
        if not source.startswith("http"):
            self.cap = cv2.VideoCapture(int(source) if source.isdigit() else source,
                                        cv2.CAP_V4L2)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(source)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

    def read(self):
        if self.cap is not None:
            ok, frame = self.cap.read()
            return frame if ok else None
        try:
            with urllib.request.urlopen(self.source, timeout=0.8) as r:
                raw = r.read()
            return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        except Exception:
            return None


def detect_obstacle(gray, bg_gray, frame_bgr, bg_bgr,
                    roi_x0, roi_x1, v_min, v_max, thr,
                    min_w=10, min_h=8, min_area=120,
                    edge_px=3, color_dv=25.0, color_ds=20.0,
                    strong_diff=55.0, model=None, half_w=0.0,
                    min_obj_m=0.012):
    """Tim cum vat can 2D gan nhat trong ROI.

    ROI hinh thang (V2.2): moi hang chi lay u trong hanh lang than xe
    |X| <= half_w => o 0,3 m phu rong ~ +-0,25 m thay vi +-0,06 m nhu ROI chu nhat.
    Neu model=None hoac half_w=0 thi giu ROI chu nhat roi_x0..roi_x1.

    Tra (u, v, width_px, area) hoac None.
    """
    h, w = gray.shape[:2]
    x0, x1 = int(roi_x0 * w), int(roi_x1 * w)
    v_lo, v_hi = max(0, int(v_min)), min(h, int(v_max))
    if x1 - x0 < 5 or v_hi - v_lo < 5:
        return None

    diff = cv2.GaussianBlur(cv2.absdiff(gray, bg_gray), (5, 5), 0)
    mask = (diff > thr).astype(np.uint8) * 255
    mask[:v_lo, :] = 0
    mask[v_hi:, :] = 0

    trapezoid = bool(model is not None and half_w and half_w > 0.01 and
                     getattr(model, "fx", 0.0) > 1.0)
    if trapezoid:
        rows = np.arange(h, dtype=np.float32)
        den = rows - float(model.v0)
        with np.errstate(divide="ignore", invalid="ignore"):
            d_rows = np.where(den > 0.5, float(model.A) / np.maximum(den, 1e-3), np.inf)
            half_px = np.where(np.isfinite(d_rows),
                               float(half_w) * float(model.fx) / np.maximum(d_rows, 1e-3),
                               0.0)
        u_lo = np.clip(float(model.cx) - half_px, 0, w)
        u_hi = np.clip(float(model.cx) + half_px, 0, w)
        cols = np.arange(w, dtype=np.float32)[None, :]
        allow = (cols >= u_lo[:, None]) & (cols <= u_hi[:, None])
        mask[~allow] = 0
    else:
        mask[:, :x0] = 0
        mask[:, x1:] = 0

    # open: diet vach gach / nhieu 1-2 pixel; close: lien ket vat bi dut
    m = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    n, labels, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    if n <= 1:
        return None

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV).astype(np.int16)
    hsv_bg = cv2.cvtColor(bg_bgr, cv2.COLOR_BGR2HSV).astype(np.int16)

    best = None
    for i in range(1, n):
        bx, by, bw, bh, area = stats[i]
        if area < min_area or bw < min_w or bh < min_h:
            continue
        if bx <= edge_px or bx + bw >= w - edge_px:
            continue          # cum cham mep ANH: khong du thong tin
        v = by + bh - 1
        if v < v_lo or v >= v_hi:
            continue
        if v >= v_hi - 3:
            continue          # cham day dai = vat sat hon min_range/bong than xe

        if model is not None:
            d_here = model.distance(v)
            if d_here is None:
                continue
            if d_here < model.lo * 0.6 or d_here > model.hi * 1.4:
                continue
            if model.fx > 1.0:
                width_m = float(bw) * d_here / float(model.fx)
                if width_m < float(min_obj_m):
                    continue  # qua hep: van san / duong chi tiet, khong phai vat
            if trapezoid:
                x_center = model.lateral(bx + bw / 2.0, d_here)
                if abs(x_center) > float(half_w) + 0.02:
                    continue  # tam vat ngoai hanh lang than xe

        comp = labels == i
        dv = float(np.mean(np.abs(hsv[:, :, 2][comp] - hsv_bg[:, :, 2][comp])))
        ds = float(np.mean(np.abs(hsv[:, :, 1][comp] - hsv_bg[:, :, 1][comp])))
        dg = float(np.mean(diff[comp]))
        # Phan chieu tren san bong giu nguyen mau va do sang thap -> loai.
        # Vat that co chenh sang manh (bong/khung) thi giu du mau giong.
        if dv < color_dv and ds < color_ds and dg < strong_diff:
            continue

        if best is None or v > best[1]:
            best = (bx + bw / 2.0, v, bw, area)

    return best


def detect_contact(gray, bg_gray, roi_x0, roi_x1, v_min, v_max, thr, min_col):
    """Tuong thich nguoc: chi dung gray (khong kiem tra mau)."""
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    bg_bgr = cv2.cvtColor(bg_gray, cv2.COLOR_GRAY2BGR)
    hit = detect_obstacle(gray, bg_gray, bgr, bg_bgr, roi_x0, roi_x1,
                          v_min, v_max, thr, min_w=max(6, int(min_col)),
                          min_h=max(4, int(min_col)), min_area=40,
                          edge_px=2, color_dv=1e9, color_ds=1e9)
    if hit is None:
        return None
    u, v, width, _ = hit
    return u, v, int(width)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calib", default=os.path.expanduser("~/camera_calib.json"))
    ap.add_argument("--bg", default=os.path.expanduser("~/floor_ref.jpg"))
    ap.add_argument("--source", default="http://127.0.0.1:8081/snapshot.jpg")
    ap.add_argument("--cam-height", type=float, default=0.0,
                    help="chieu cao camera so voi san (m), de tinh lech ngang X")
    ap.add_argument("--hz", type=float, default=10.0)
    ap.add_argument("--roi", default="0.35,0.65", help="dai ngang tim vat (ti le anh)")
    ap.add_argument("--thr", type=int, default=28, help="nguong chenh lech 0-255")
    ap.add_argument("--min-col", type=int, default=6,
                    help="(tuong thich) so pixel doc toi thieu")
    ap.add_argument("--min-w", type=int, default=10, help="do rong cum toi thieu (pixel)")
    ap.add_argument("--min-h", type=int, default=10, help="chieu cao cum toi thieu (pixel)")
    ap.add_argument("--min-area", type=int, default=200, help="dien tich cum toi thieu")
    ap.add_argument("--edge-px", type=int, default=3, help="bo qua cum cham mep anh")
    ap.add_argument("--half-w", type=float, default=0.25,
                    help="nua hanh lang than xe (m) cho ROI hinh thang; 0 = ROI chu nhat")
    ap.add_argument("--min-obj-m", type=float, default=0.020,
                    help="be rong toi thieu cua vat that (m); nho hon = nhieu san")
    ap.add_argument("--min-range", type=float, default=0.25,
                    help="bo qua vung sat hon min_range (m): chan xe, bong/van san")
    ap.add_argument("--max-range", type=float, default=0.80,
                    help="chi tim vat trong khoang min_range..max_range (m)")
    ap.add_argument("--color-dv", type=float, default=25.0,
                    help="nguong chenh do sang V de coi la vat that")
    ap.add_argument("--color-ds", type=float, default=20.0,
                    help="nguong chenh bao hoa S de coi la vat that")
    ap.add_argument("--debug", default="", help="ghi anh chan doan ra file nay (JPG)")
    args = ap.parse_args()

    if not os.path.exists(args.calib):
        sys.exit("Khong thay file hieu chuan: %s" % args.calib)
    if not os.path.exists(args.bg):
        sys.exit("Khong thay anh nen: %s" % args.bg)

    model = RangeModel(args.calib, args.cam_height)
    print("[cam_range] A=%.1f v0=%.1f rms=%.3f cx=%.1f fx=%.1f valid=%.2f-%.2f m"
          % (model.A, model.v0, model.rms, model.cx, model.fx, model.lo, model.hi))

    bg_raw = cv2.imread(args.bg, cv2.IMREAD_GRAYSCALE)
    bg_raw_bgr = cv2.imread(args.bg, cv2.IMREAD_COLOR)
    if bg_raw is None or bg_raw_bgr is None:
        sys.exit("Khong doc duoc anh nen: %s" % args.bg)

    grabber = FrameGrabber(args.source)
    rx0, rx1 = [float(v) for v in args.roi.split(",")]
    state = {"bg": None, "bg_bgr": None, "last": None}

    def step():
        frame = grabber.read()
        if frame is None:
            state["last"] = None
            return CLEAR_VALUE, 0.0, None, None, None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        bg = state["bg"]
        bg_bgr = state["bg_bgr"]
        if bg is None or bg.shape != gray.shape:
            bg = cv2.resize(bg_raw, (gray.shape[1], gray.shape[0]))
            bg = cv2.GaussianBlur(bg, (5, 5), 0)
            bg_bgr = cv2.resize(bg_raw_bgr, (gray.shape[1], gray.shape[0]))
            state["bg"] = bg
            state["bg_bgr"] = bg_bgr

        # can bang sang toan cuc: bu thay doi anh sang ngay/dem, auto-exposure
        try:
            mg = float(gray.mean())
            mb = float(bg.mean())
            if mg > 5.0 and mb > 5.0:
                gain = mb / mg
                if 0.75 <= gain <= 1.35:
                    gray = np.clip(gray.astype(np.float32) * gain, 0, 255).astype(np.uint8)
        except Exception:
            pass

        v_bottom = int(model.v0 + model.A / max(0.05, args.min_range))
        v_bottom = max(int(model.v0) + 10, min(gray.shape[0] - 2, v_bottom))
        v_top = int(model.v0 + model.A / max(args.min_range + 0.05, args.max_range))
        v_top = max(int(model.v0) + 3, min(v_bottom - 10, v_top))
        hit = detect_obstacle(gray, bg, frame, bg_bgr, rx0, rx1, v_top,
                              v_bottom, args.thr, args.min_w, args.min_h,
                              args.min_area, args.edge_px, args.color_dv,
                              args.color_ds, model=model, half_w=args.half_w,
                              min_obj_m=args.min_obj_m)
        if hit is None:
            state["last"] = None
            state["support"] = 0
            return CLEAR_VALUE, 0.0, None, None, gray

        u, v, support, _area = hit
        state["support"] = support
        d = model.distance(v)
        if d is None or d < model.lo * 0.6 or d > model.hi * 1.4:
            state["last"] = None
            state["support"] = 0
            return CLEAR_VALUE, 0.0, None, None, gray
        x = model.lateral(u, d)
        state["last"] = (d, x, u, v)
        return d, x, u, v, gray

    if HAVE_ROS:
        rclpy.init()
        node = Node("cam_range")
        pub_r = node.create_publisher(Float32, "/cam_range", 10)
        pub_p = node.create_publisher(PointStamped, "/cam_obstacle", 10)
        pub_bg = node.create_publisher(Float32, "/cam_bg_diff", 10)
        pub_frac = node.create_publisher(Float32, "/cam_bg_frac", 10)
        pub_sup = node.create_publisher(Float32, "/cam_support", 10)

        def on_capture(_msg):
            # Chup lai anh nen ngay lap tuc, khong can restart node.
            try:
                frame = grabber.read()
                if frame is None:
                    print("[cam_range] chup nen: khong co frame", flush=True)
                    return
                g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                g = cv2.GaussianBlur(g, (5, 5), 0)
                state["bg"] = g
                state["bg_bgr"] = cv2.resize(frame, (g.shape[1], g.shape[0]))
                try:
                    cv2.imwrite(args.bg, frame)
                except Exception:
                    pass
                print("[cam_range] da chup lai anh nen", flush=True)
            except Exception as exc:
                print("[cam_range] chup nen loi:", exc, flush=True)

        node.create_subscription(Empty, "/cam_capture_bg", on_capture, 10)

        def on_timer():
            if not rclpy.ok():
                return
            try:
                d, x, u, v, gray = step()
            except Exception:
                return
            msg = Float32()
            msg.data = float(d)
            try:
                pub_r.publish(msg)
                sup = Float32()
                sup.data = float(state.get("support", 0) or 0)
                pub_sup.publish(sup)
            except Exception:
                return
            if u is not None:
                p = PointStamped()
                p.header.stamp = node.get_clock().now().to_msg()
                p.header.frame_id = "base_footprint"
                p.point.x = float(x)
                p.point.y = float(d)
                p.point.z = float(state.get("support", 0) or 0)
                try:
                    pub_p.publish(p)
                except Exception:
                    return
            if gray is not None and state.get("bg") is not None:
                try:
                    n_frame = state.get("n_frame", 0) + 1
                    state["n_frame"] = n_frame
                    if n_frame % 10 == 1:
                        h, w = gray.shape[:2]
                        bg = state["bg"]
                        x0, x1 = int(0.35 * w), int(0.65 * w)
                        # Chi do trong dai an toan 0.20-0.60 m: dong do phia xa
                        # (nguoi di lai, do dac) khong lam sai chi so nen.
                        v_top = int(round(model.v0 + model.A / 0.60))
                        v_bot = int(round(model.v0 + model.A / 0.20))
                        v_top = max(int(model.v0) + 3, min(h - 3, v_top))
                        v_bot = max(v_top + 2, min(h - 2, v_bot))
                        d_roi = cv2.absdiff(gray, bg)[v_top:v_bot, x0:x1]
                        m = Float32()
                        m.data = float(d_roi.mean())
                        pub_bg.publish(m)
                        # ti le PIXEL khac nen trong dai an toan (0..1)
                        frac = float((d_roi > args.thr).mean())
                        f = Float32()
                        f.data = frac
                        pub_frac.publish(f)
                except Exception:
                    pass
            if args.debug and gray is not None:
                dbg = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                if v is not None:
                    cv2.circle(dbg, (int(u), int(v)), 6, (0, 255, 0), 2)
                    cv2.putText(dbg, "%.2fm x=%.2fm" % (d, x), (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                else:
                    cv2.putText(dbg, "clear", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
                cv2.imwrite(args.debug, dbg)

        node.create_timer(1.0 / max(1.0, args.hz), on_timer)
        print("[cam_range] publish /cam_range, /cam_obstacle @ %.1f Hz" % args.hz)
        try:
            rclpy.spin(node)
        except (KeyboardInterrupt, ExternalShutdownException):
            pass
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            try:
                node.destroy_node()
            except Exception:
                pass
            if rclpy.ok():
                rclpy.shutdown()
        return

    print("[cam_range] khong co rclpy -> in ra man hinh")
    period = 1.0 / max(1.0, args.hz)
    try:
        while True:
            t0 = time.time()
            d, x, u, v, _ = step()
            if u is None:
                print("d=clear")
            else:
                print("d=%.3f m  x=%+.3f m  (u=%.0f v=%.0f)" % (d, x, u, v))
            rest = period - (time.time() - t0)
            if rest > 0:
                time.sleep(rest)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

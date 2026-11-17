#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lop chan vat can bang camera, bo tro cho LiDAR 2D.

LiDAR 2D chi quet mot mat phang o do cao cua no, nen vat thap hon (day dien,
canh hop, chan ban, mep tha dam) nam duoi mat phang quet se khong thay.
Camera da hieu chuan do khoang cach toi diem tiep xuc san, lap day diem mu do.

Chinh sach moi (V2.1):
  - Vat can NHO (rong < small_max_m, vd day dien, chan ban, do choi):
      DUNG HAN tai cho (V 0 0), cho den khi vat duoc lay di (d > clear_m)
      roi TU DONG tiep tuc nhiem vu dang chay.
  - Vat can TO (rong >= small_max_m, vd thung, ghe, balo):
      coi nhu vat can thuong -> quay tim huong vong / doi muc tieu,
      giong logic LiDAR cua ban cu.
  - Chi chan chieu TIEN (v > 0). Lui / quay khong bi anh huong.
  - Du lieu cu qua timeout_s -> BO QUA camera (fail-open), LiDAR van chay.
    Rieng khi dang CHO vat nho: mat du lieu camera van tiep tuc dung yen.
  - Tre 15 cm giua nguong chan va nguong nha (hysteresis) de khong rung.
  - Chi chan khi vat nam trong hanh lang than xe (|x| <= half_w).
  - Khong bao gio tu ARM, khong tu chay.

Nhan tu cam_range_node.py:
  /cam_range     sensor_msgs/Float32   (m); 9.9 = duong trong
  /cam_obstacle  geometry_msgs/PointStamped  x = lech ngang, y = khoang cach,
                                             z = do rong cum (pixel)
  /cam_bg_diff   sensor_msgs/Float32   do lech trung binh so voi anh nen
  /cam_bg_frac   sensor_msgs/Float32   ti le cot ROI khac nen (0..1)
"""

import json
import math
import os
import time

CLEAR_VALUE = 9.9
SMALL_CLASS = "small"
LARGE_CLASS = "large"


class CamAvoid:
    def __init__(self, enabled=True, stop_m=0.30, clear_m=0.45, half_w=0.25,
                 timeout_s=2.0, config_path=None, bg_max_diff=20.0,
                 bg_frac_max=0.20, small_max_m=0.15, fx_px=457.4):
        self.enabled = bool(enabled)
        self.stop_m = float(stop_m)
        self.clear_m = float(clear_m)
        self.half_w = float(half_w)
        self.timeout_s = float(timeout_s)
        self.bg_max_diff = float(bg_max_diff)
        self.bg_frac_max = float(bg_frac_max)
        self.small_max_m = float(small_max_m)
        self.fx_px = float(fx_px)
        self.config_path = config_path

        self.d = None          # khoang cach moi nhat (m)
        self.x = 0.0           # lech ngang moi nhat (m)
        self.mono = 0.0        # thoi diem nhan
        self.blocked = False   # trang thai co tre (hysteresis)
        self.reason = None
        self.block_count = 0   # so lan lien tiep bi chan
        self.support = 0       # do rong cum vat can (so cot pixel)
        self.bg_diff = None    # do lech trung binh giua anh nen va hien tai
        self.bg_frac = None    # ti le cot ROI khac nen (0..1)
        self.bg_mono = 0.0
        self.bg_frac_mono = 0.0
        self.stable_count = 0  # so khung lien tiep thay cung mot vat
        self.stable_mono = 0.0
        self.last_block_mono = 0.0

        self.hit_class = None  # 'small' | 'large'
        self.width_m = None    # do rong uoc luong cua vat (m)
        self.wait_since = None  # thoi diem bat dau CHO vat nho

        self._load()

    # ---------------- cau hinh ----------------
    def _load(self):
        if not self.config_path or not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as fh:
                c = json.load(fh)
            self.enabled = bool(c.get("enabled", self.enabled))
            self.stop_m = float(c.get("stop_m", self.stop_m))
            self.clear_m = float(c.get("clear_m", self.clear_m))
            self.half_w = float(c.get("half_w", self.half_w))
            self.timeout_s = float(c.get("timeout_s", self.timeout_s))
            self.small_max_m = float(c.get("small_max_m", self.small_max_m))
            self.bg_frac_max = float(c.get("bg_frac_max", self.bg_frac_max))
        except Exception:
            pass

    def persist_config(self):
        if not self.config_path:
            return
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as fh:
                json.dump({"enabled": self.enabled, "stop_m": self.stop_m,
                           "clear_m": self.clear_m, "half_w": self.half_w,
                           "timeout_s": self.timeout_s,
                           "small_max_m": self.small_max_m,
                           "bg_frac_max": self.bg_frac_max}, fh, indent=2)
        except Exception:
            pass

    # ---------------- nap du lieu ----------------
    def feed_range(self, d, now=None):
        now = time.monotonic() if now is None else now
        try:
            d = float(d)
        except (TypeError, ValueError):
            return
        if not math.isfinite(d) or d <= 0:
            return
        self.d = d
        if d >= CLEAR_VALUE - 0.5:
            self.x = 0.0
            if self.reason == 'CAM_WAIT':
                # Camera bao duong trong -> thoi trang thai cho
                self._set_clear()
        self.mono = now
        # do on dinh: vat phai duoc thay lien tuc vai khung
        if self._is_clear(d) or d > max(0.45, self.stop_m * 1.4):
            self.stable_count = 0
        else:
            if now - self.stable_mono <= 0.40:
                self.stable_count += 1
            else:
                self.stable_count = 1
            self.stable_mono = now

    def feed_bg(self, v, now=None):
        now = time.monotonic() if now is None else now
        try:
            v = float(v)
        except (TypeError, ValueError):
            return
        if math.isfinite(v):
            self.bg_diff = v
            self.bg_mono = now

    def feed_bg_frac(self, v, now=None):
        now = time.monotonic() if now is None else now
        try:
            v = float(v)
        except (TypeError, ValueError):
            return
        if not math.isfinite(v):
            return
        if v > 1.5:          # phong khi node cu phat theo %
            v = v / 100.0
        self.bg_frac = max(0.0, min(1.0, v))
        self.bg_frac_mono = now

    def feed_support(self, n):
        try:
            self.support = max(0, int(float(n)))
        except (TypeError, ValueError):
            self.support = 0

    def feed_obstacle(self, x, d=None, now=None):
        now = time.monotonic() if now is None else now
        try:
            x = float(x)
        except (TypeError, ValueError):
            return
        if not math.isfinite(x):
            return
        self.x = x
        if d is not None:
            try:
                dd = float(d)
                if math.isfinite(dd) and dd > 0:
                    self.d = dd
                    self.mono = now
            except (TypeError, ValueError):
                pass

    # ---------------- danh gia ----------------
    def bg_stale(self, now=None):
        """Nen lech qua nhieu => camera khong dang tin (xe da doi cho)."""
        now = time.monotonic() if now is None else now
        if self.bg_diff is not None and self.bg_mono and (now - self.bg_mono) <= 5.0:
            if self.bg_diff > self.bg_max_diff:
                return True
        if self.bg_frac is not None and self.bg_frac_mono and (now - self.bg_frac_mono) <= 5.0:
            if self.bg_frac > self.bg_frac_max:
                return True
        return False

    def age(self, now=None):
        now = time.monotonic() if now is None else now
        return None if not self.mono else now - self.mono

    def _is_clear(self, d):
        return d is None or not math.isfinite(d) or d >= CLEAR_VALUE - 0.5

    def classify(self):
        """Phan loai vat: (class, width_m). Khong ro -> coi la nho (an toan)."""
        d = self.d
        if self._is_clear(d):
            return None, None
        if self.support <= 0 or self.fx_px <= 1.0:
            return SMALL_CLASS, None
        width = float(self.support) * float(d) / self.fx_px
        return (SMALL_CLASS if width < self.small_max_m else LARGE_CLASS), width

    def contact(self, now=None):
        """Tra (d, x) neu camera dang thay mot vat that, on dinh va nen khop."""
        now = time.monotonic() if now is None else now
        if not self.enabled or self.bg_stale(now):
            return None
        if not self.mono or (now - self.mono) > self.timeout_s:
            return None
        if self._is_clear(self.d):
            return None
        if self.stable_count < 5:          # ~0.5 giay o 10 Hz
            return None
        if self.d > max(0.45, self.stop_m * 1.4):
            return None
        return (float(self.d), float(self.x))

    def _set_clear(self):
        self.blocked = False
        self.reason = None
        self.block_count = 0
        self.hit_class = None
        self.wait_since = None

    def gate(self, v, now=None):
        """Tra ve (allow, reason, info).

        reason:
          'CAM_WAIT'  -> vat nho: dung han, cho lay di
          'CAM_OBSTACLE' -> vat to: chan chieu tien, cho phep quay/lui
        """
        now = time.monotonic() if now is None else now
        info = {"enabled": self.enabled, "d": self.d, "x": self.x,
                "age_s": (round(self.age(now), 3) if self.mono else None),
                "stop_m": self.stop_m, "clear_m": self.clear_m,
                "half_w": self.half_w, "support": self.support,
                "small_max_m": self.small_max_m}

        if not self.enabled:
            self._set_clear()
            info["status"] = "DISABLED"
            return True, None, info

        try:
            v = float(v)
        except (TypeError, ValueError):
            return True, None, info

        # chi ap dung cho chieu tien
        if not math.isfinite(v) or v <= 0.005:
            # Dang cho vat nho thi giu nguyen trang thai (V 0 0 do vong
            # tu hanh gui moi 0.1 s, khong duoc xoa co "dang cho").
            if self.reason != 'CAM_WAIT':
                self._set_clear()
            info["status"] = "NOT_FORWARD"
            return True, None, info

        if self.bg_stale(now):
            # Nen lech: khong tin duoc so do chinh xac, NHUNG neu co vat
            # rong (nhieu cot pixel) va rat gan thi van phai dung cho.
            close = (not self._is_clear(self.d)) and self.d <= max(0.35, self.stop_m + 0.05)
            wide = self.support >= 12
            if close and wide and abs(self.x) <= self.half_w:
                self.blocked = True
                self.reason = 'CAM_WAIT'
                self.block_count += 1
                self.hit_class = LARGE_CLASS
                if self.wait_since is None:
                    self.wait_since = now
                info["status"] = "WAIT_STALE_BG"
                info["support"] = self.support
                info["bg_diff"] = (round(self.bg_diff, 1)
                                   if self.bg_diff is not None else None)
                info["bg_frac"] = (round(self.bg_frac, 3)
                                   if self.bg_frac is not None else None)
                info["class"] = LARGE_CLASS
                return False, 'CAM_WAIT', info
            self._set_clear()
            info["status"] = "BG_STALE"
            info["bg_diff"] = (round(self.bg_diff, 1)
                               if self.bg_diff is not None else None)
            info["bg_frac"] = (round(self.bg_frac, 3)
                               if self.bg_frac is not None else None)
            info["support"] = self.support
            return True, None, info

        age = self.age(now)
        if age is None or age > self.timeout_s:
            # Dang cho vat nho ma mat du lieu -> van dung yen (an toan),
            # khong fail-open de lao vao vat da thay truoc do.
            if self.reason == 'CAM_WAIT' and not self._is_clear(self.d):
                info["status"] = "WAIT_NO_DATA"
                info["class"] = self.hit_class or SMALL_CLASS
                return False, 'CAM_WAIT', info
            self._set_clear()
            info["status"] = "NO_DATA"
            return True, None, info

        if self._is_clear(self.d):
            self._set_clear()
            info["status"] = "CLEAR"
            return True, None, info

        lateral_ok = abs(self.x) <= self.half_w
        threshold = self.clear_m if self.blocked else self.stop_m
        if lateral_ok and self.d <= threshold:
            cls, width = self.classify()
            self.hit_class = cls or SMALL_CLASS
            self.width_m = width
            if self.hit_class == SMALL_CLASS:
                if self.wait_since is None:
                    self.wait_since = now
                self.blocked = True
                self.reason = 'CAM_WAIT'
                self.block_count += 1
                self.last_block_mono = now
                info["status"] = "WAIT"
                info["class"] = SMALL_CLASS
                info["width_m"] = width
                info["wait_s"] = round(now - self.wait_since, 2)
                return False, 'CAM_WAIT', info

            self.blocked = True
            self.reason = "CAM_OBSTACLE"
            self.block_count += 1
            self.last_block_mono = now
            info["status"] = "BLOCKED"
            info["class"] = LARGE_CLASS
            info["width_m"] = width
            return False, "CAM_OBSTACLE", info

        self._set_clear()
        info["status"] = "CLEAR"
        return True, None, info

    def gate_cmd(self, cmd, now=None):
        """Chan lenh 'V v w' / 'M l r' neu camera thay vat can thap phia truoc."""
        clean = (cmd or "").strip()
        v = None
        if clean.startswith("V "):
            parts = clean.split()
            if len(parts) >= 2:
                try:
                    v = float(parts[1])
                except ValueError:
                    v = None
        elif clean.startswith("M "):
            parts = clean.split()
            if len(parts) >= 3:
                try:
                    v = (float(parts[1]) + float(parts[2])) / 2.0
                except ValueError:
                    v = None
        if v is None:
            return True, None, {"status": "NOT_APPLICABLE"}
        return self.gate(v, now)

    def wait_state(self, now=None):
        """Tra dict neu dang phai dung cho vat can nho, nguoc lai None.

        Tu danh gia contact hien tai (khong phu thuoc lan gate truoc do) de
        vong tu hanh dung duoc ngay ca khi chua gui lenh tien nao.
        Tu dong nha khi vat da duoc lay di (d > clear_m, co tre) hoac vat
        ra khoi hanh lang than xe. Mat du lieu camera van tiep tuc cho.
        """
        now = time.monotonic() if now is None else now
        if not self.enabled:
            return None
        if self.bg_stale(now):
            if self.reason == 'CAM_WAIT':
                self._set_clear()
            return None
        waiting = (self.reason == 'CAM_WAIT')

        if self._is_clear(self.d):
            if waiting:
                self._set_clear()
            return None
        if abs(self.x) > self.half_w:
            if waiting:
                self._set_clear()
            return None

        stale = (not self.mono) or (now - self.mono) > self.timeout_s
        if not stale:
            cls, width = self.classify()
            if cls != SMALL_CLASS:
                if waiting:
                    self._set_clear()
                return None
            threshold = self.clear_m if waiting else self.stop_m
            if self.d > threshold:
                if waiting:
                    self._set_clear()
                return None
            if not waiting and self.stable_count < 2:
                return None
            self.blocked = True
            self.reason = 'CAM_WAIT'
            self.hit_class = SMALL_CLASS
            self.width_m = width
        elif not waiting:
            return None      # mat du lieu khi chua tung cho -> fail-open

        if self.wait_since is None:
            self.wait_since = now
        cls, width = self.classify()
        return {"d": self.d, "x": self.x,
                "class": cls or self.hit_class or SMALL_CLASS,
                "width_m": width, "wait_s": round(now - self.wait_since, 1),
                "stale": bool(stale)}

    def simulate(self, v, d, x=0.0, support=None):
        """Kiem tra logic khong can phan cung (d=None -> dung gia tri hien tai)."""
        sd, sx, sm = self.d, self.x, self.mono
        ss, sr, sb, sc = self.support, self.reason, self.blocked, self.hit_class
        sws = self.wait_since
        try:
            if d is not None:
                self.d = float(d)
                self.x = float(x)
                self.mono = time.monotonic()
            if support is not None:
                self.support = max(0, int(float(support)))
            allow, reason, info = self.gate(v)
        finally:
            self.d, self.x, self.mono = sd, sx, sm
            self.support, self.reason, self.blocked, self.hit_class = ss, sr, sb, sc
            self.wait_since = sws
        info["simulated_d"] = d
        info["simulated_x"] = x
        if support is not None:
            info["simulated_support"] = support
        return allow, reason, info

    def reset(self):
        self._set_clear()

    def snapshot(self):
        now = time.monotonic()
        fresh = bool(self.mono) and (now - self.mono) <= self.timeout_s
        bg_stale = self.bg_stale(now)
        cls, width = self.classify()
        if bg_stale:
            # Nen lech: chi coi la vat can khi vat rong va rat gan.
            obstacle = bool(fresh and self.enabled and not self._is_clear(self.d)
                            and abs(self.x) <= self.half_w and self.support >= 12
                            and self.d <= max(0.35, self.stop_m + 0.05))
        else:
            obstacle = bool(fresh and self.enabled and not self._is_clear(self.d)
                            and abs(self.x) <= self.half_w and self.d <= self.stop_m)
        waiting = bool(self.enabled and self.reason == 'CAM_WAIT' and
                       (self.wait_since is not None) and
                       (not self._is_clear(self.d)))
        return {
            "enabled": self.enabled,
            "stop_m": self.stop_m,
            "clear_m": self.clear_m,
            "half_w": self.half_w,
            "timeout_s": self.timeout_s,
            "small_max_m": self.small_max_m,
            "d": self.d,
            "x": self.x,
            "age_s": (round(self.age(now), 3) if self.mono else None),
            "blocked": self.blocked,
            "obstacle": obstacle,
            "reason": self.reason,
            "class": cls,
            "width_m": (round(width, 3) if width is not None else None),
            "waiting": waiting,
            "wait_s": (round(now - self.wait_since, 1)
                       if (waiting and self.wait_since is not None) else None),
            "block_count": self.block_count,
            "stable_count": self.stable_count,
            "support": self.support,
            "bg_diff": (round(self.bg_diff, 1)
                        if (self.bg_mono and now - self.bg_mono <= 5.0) else None),
            "bg_frac": (round(self.bg_frac, 3)
                        if (self.bg_frac_mono and now - self.bg_frac_mono <= 5.0) else None),
            "bg_ok": not bg_stale,
            "bg_max_diff": self.bg_max_diff,
            "bg_frac_max": self.bg_frac_max,
        }

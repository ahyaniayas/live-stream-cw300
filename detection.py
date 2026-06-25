"""FrameGrabber, Detector (YOLO), dan MJPEG stream generator."""
import os
import time
import threading

import cv2
import numpy as np

import state
from config import (
    STREAM_URL, DETECT_CONF, DETECT_MAX_FPS, STREAM_MAX_FPS,
    YOLO_MODEL, GATE_TARGET_LABELS, label_category, log,
)
import zones as zone_mod


class FrameGrabber:
    def __init__(self, url):
        self.url       = url
        self.lock      = threading.Lock()
        self.frame     = None
        self.connected = False
        self.running   = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, 2)
            os.close(devnull)
        except Exception:
            pass

        while self.running:
            log(f"Membuka RTSP: {self.url}")
            cap = cv2.VideoCapture(self.url)
            _logged = False
            while self.running:
                ok, frame = cap.read()
                if not ok:
                    log("Frame gagal dibaca, reconnect...")
                    with self.lock:
                        self.frame     = None
                        self.connected = False
                    break
                if np.std(frame) < 8:
                    continue
                if not _logged:
                    rw = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    rh = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    rf = cap.get(cv2.CAP_PROP_FPS)
                    fps_str = f"{rf:.1f} fps" if rf > 0 else "fps tidak diketahui"
                    log(f"RTSP terhubung: {int(rw)}x{int(rh)} @ {fps_str}")
                    _logged = True
                with self.lock:
                    self.frame     = frame
                    self.connected = True
            cap.release()
            time.sleep(1.0)

    def read(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()


def get_model():
    if state._model is None:
        with state._model_lock:
            if state._model is None:
                import torch
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                log(f"Memuat model YOLO: {YOLO_MODEL} (device: {device})")
                from ultralytics import YOLO
                state._model = YOLO(YOLO_MODEL)
                state._model.to(device)
                log("Model YOLO siap")
    return state._model


class Detector:
    def __init__(self, grabber: FrameGrabber):
        self.grabber = grabber
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        interval = 1.0 / DETECT_MAX_FPS
        while self.running:
            t0 = time.monotonic()
            try:
                with state._detect_lock:
                    do_detect = state._detect_on

                if not do_detect:
                    with state._detect_lock:
                        state._last_dets.clear()
                    with state._last_boxes_lock:
                        state._last_boxes.clear()
                    with state._zones_lock:
                        for z in state._zones.values():
                            z["active"] = False
                            z["current_count"] = 0
                    time.sleep(0.1)
                    continue

                frame = self.grabber.read()
                if frame is None:
                    time.sleep(0.05)
                    continue

                results = get_model()(frame, conf=DETECT_CONF, verbose=False)
                h, w    = frame.shape[:2]

                dets             = []
                person_positions = []
                box_data         = []

                with state._cat_lock:
                    cat_en = {
                        "person":  state._cat_person,
                        "vehicle": state._cat_vehicle,
                        "other":   state._cat_other,
                    }

                for box in results[0].boxes:
                    label = results[0].names[int(box.cls[0])]
                    if not cat_en.get(label_category(label), True):
                        continue
                    conf  = float(box.conf[0])
                    dets.append({"label": label, "conf": round(conf, 2)})

                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                    if label in GATE_TARGET_LABELS:
                        person_positions.append((x1, y1, x2, y2))

                    in_any_zone = False
                    if label in GATE_TARGET_LABELS:
                        with state._zones_lock:
                            for z in state._zones.values():
                                if not z["points"]:
                                    continue
                                pts = np.array(
                                    [[int(p[0]*w), int(p[1]*h)] for p in z["points"]],
                                    dtype=np.int32,
                                )
                                if zone_mod.bbox_intersects_zone(pts, x1, y1, x2, y2):
                                    in_any_zone = True
                                    break

                    box_data.append((x1, y1, x2, y2, label, conf, in_any_zone))

                with state._last_boxes_lock:
                    state._last_boxes[:] = box_data
                with state._detect_lock:
                    state._last_dets.clear()
                    state._last_dets.extend(dets)

                zone_mod.update_zones(person_positions, h, w, frame)
                log(f"Deteksi: {[d['label'] for d in dets]}")

            except Exception as exc:
                log(f"Detector error: {exc}")
                time.sleep(1.0)

            elapsed = time.monotonic() - t0
            wait    = interval - elapsed
            if wait > 0:
                time.sleep(wait)


def ensure_started():
    if state._detector is not None:
        return
    with state._init_lock:
        if state._detector is not None:
            return
        log("Memulai FrameGrabber dan Detector...")
        state._grabber  = FrameGrabber(STREAM_URL)
        state._detector = Detector(state._grabber)


def mjpeg_stream():
    ensure_started()

    fps_t       = time.monotonic()
    fps_count   = 0
    frame_t     = time.monotonic()
    frame_delay = 1.0 / STREAM_MAX_FPS

    while True:
        try:
            # Selalu ambil frame segar dari grabber agar stream tetap smooth
            # meskipun DETECT_MAX_FPS rendah
            out = state._grabber.read()
            if out is None:
                time.sleep(0.05)
                continue

            with state._detect_lock:
                do_detect = state._detect_on

            if do_detect:
                with state._overlay_lock:
                    show_b = state._show_boxes
                    show_n = state._show_names
                with state._last_boxes_lock:
                    boxes = list(state._last_boxes)
                for (x1, y1, x2, y2, label, conf, in_zone) in boxes:
                    color = (0, 0, 220) if in_zone else (0, 220, 0)
                    if show_b:
                        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
                    if show_n:
                        cv2.putText(out, f"{label} {conf:.2f}",
                                    (x1, max(y1 - 6, 15)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

            out = zone_mod.draw_zones(out)
            fps_count += 1

            ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                continue

            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

            now = time.monotonic()
            if now - fps_t >= 1.0:
                state._stream_fps = round(fps_count / (now - fps_t))
                log(f"Stream FPS: {state._stream_fps}")
                fps_count = 0
                fps_t     = now

            elapsed = time.monotonic() - frame_t
            wait    = frame_delay - elapsed
            if wait > 0:
                time.sleep(wait)
            frame_t = time.monotonic()

        except GeneratorExit:
            return
        except Exception as exc:
            log(f"Stream error: {exc}")
            time.sleep(0.1)

"""Logika zona: cek bbox, update state, gambar overlay."""
import queue
import time

import cv2
import numpy as np

import state
import telegram
from config import GATE_ALERT_COOLDOWN, GATE_DEACTIVATE_SEC, log
import database


def bbox_intersects_zone(pts, x1, y1, x2, y2):
    """True jika salah satu dari 5 titik bbox berada di dalam polygon."""
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    for pt in [(x1, y1), (x2, y1), (x1, y2), (x2, y2), (cx, cy)]:
        if cv2.pointPolygonTest(pts, (float(pt[0]), float(pt[1])), False) >= 0:
            return True
    return False


def update_zones(person_positions, frame_h, frame_w, frame=None):
    now        = time.monotonic()
    to_persist = []
    to_notify  = []

    with state._notif_lock:
        notif_interval = state._notif_settings["interval"]

    with state._zones_lock:
        for zid, z in state._zones.items():
            if not z["points"]:
                z["active"] = z["current_count"] = 0
                continue

            pts = np.array(
                [[int(p[0] * frame_w), int(p[1] * frame_h)] for p in z["points"]],
                dtype=np.int32,
            )
            in_zone = sum(
                1 for (x1, y1, x2, y2) in person_positions
                if bbox_intersects_zone(pts, x1, y1, x2, y2)
            )
            z["current_count"] = in_zone

            if in_zone > 0:
                z["last_seen"] = now
                z["active"]    = True
                if now - z["last_trigger"] >= GATE_ALERT_COOLDOWN:
                    z["last_trigger"] = now
                    z["total_count"] += 1
                    to_persist.append((zid, z["total_count"]))
                    log(f"ALERT [{z['name']}]: {in_zone} orang | total={z['total_count']}")

                if z.get("notify"):
                    cfg  = telegram.is_configured()
                    win  = telegram.is_in_time_window()
                    sisa = notif_interval - (now - z.get("last_notif", 0.0))
                    log(f"NOTIF [{z['name']}]: configured={cfg} window={win} "
                        f"cooldown_sisa={max(0, sisa):.0f}s")
                    if cfg and win and sisa <= 0:
                        z["last_notif"] = now
                        to_notify.append((z["name"], in_zone))
            else:
                if z["active"] and now - z["last_seen"] >= GATE_DEACTIVATE_SEC:
                    z["active"] = False

    for zid, count in to_persist:
        database.upsert_zone_count(zid, count)

    for zname, count in to_notify:
        try:
            state._notif_queue.put_nowait(
                (zname, count, frame.copy() if frame is not None else None)
            )
        except queue.Full:
            log("Notif queue penuh, lewati")


def draw_zones(frame):
    with state._overlay_lock:
        show_boxes = state._show_boxes
        show_names = state._show_names

    with state._zones_lock:
        zones = list(state._zones.values())

    from config import zone_color
    for z in zones:
        if not z["points"]:
            continue
        h, w = frame.shape[:2]
        pts  = np.array(
            [[int(p[0] * w), int(p[1] * h)] for p in z["points"]],
            dtype=np.int32,
        )
        color = zone_color(z["id"], z["active"])

        if show_boxes:
            overlay = frame.copy()
            cv2.fillPoly(overlay, [pts], color)
            cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)
            cv2.polylines(frame, [pts], True, color, 2)

        if show_names:
            lx = int(pts[:, 0].min())
            ly = max(int(pts[:, 1].min()) - 10, 20)
            label = f"!! {z['name']} !!" if z["active"] else z["name"]
            cv2.putText(frame, label, (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            if z["current_count"] > 0:
                cv2.putText(frame, f"{z['current_count']} orang",
                            (lx, ly + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    return frame

import time

from flask import Blueprint, Response, jsonify, render_template, request

import state
import detection
import telegram
import database

bp = Blueprint("stream", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/video_feed")
def video_feed():
    return Response(detection.mjpeg_stream(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@bp.route("/status")
def status():
    with state._detect_lock:
        dets = list(state._last_dets)
        on   = state._detect_on
    with state._overlay_lock:
        show_boxes = state._show_boxes
        show_names = state._show_names
    with state._cat_lock:
        categories = {
            "person":  state._cat_person,
            "vehicle": state._cat_vehicle,
            "other":   state._cat_other,
        }
    counts = {}
    for d in dets:
        counts[d["label"]] = counts.get(d["label"], 0) + 1
    with state._notif_lock:
        notif_interval   = state._notif_settings["interval"]
        notif_always_on  = state._notif_settings.get("always_on",  False)
        notif_time_start = state._notif_settings["time_start"]
        notif_time_end   = state._notif_settings["time_end"]
        notif_send_photo = state._notif_settings.get("send_photo", True)
        notif_send_video = state._notif_settings.get("send_video", False)
        notif_history    = list(state._notif_history)

    # Sisa cooldown = interval - (now - last_notif) dari zona manapun yang pernah notif
    now = time.monotonic()
    cooldown = 0
    with state._zones_lock:
        for z in state._zones.values():
            if z.get("last_notif", 0.0) > 0:
                remaining = notif_interval - (now - z["last_notif"])
                if remaining > cooldown:
                    cooldown = remaining
    cooldown = max(0, int(cooldown))

    connected = state._grabber.connected if state._grabber is not None else False
    with state._stream_lock:
        stream_on = state._stream_on
    return jsonify(
        enabled=on, detections=dets, counts=counts, fps=state._stream_fps,
        stream_on=stream_on, stream_connected=connected,
        show_boxes=show_boxes, show_names=show_names,
        categories=categories,
        notif_interval=notif_interval,
        notif_always_on=notif_always_on,
        notif_in_window=telegram.is_in_time_window(),
        notif_time_start=notif_time_start,
        notif_time_end=notif_time_end,
        notif_cooldown=cooldown,
        notif_send_photo=notif_send_photo,
        notif_send_video=notif_send_video,
        notif_history=notif_history,
    )


@bp.route("/stream/toggle", methods=["POST"])
def stream_toggle():
    with state._stream_lock:
        state._stream_on = not state._stream_on
        s = state._stream_on
    database.set_setting("stream_on", "true" if s else "false")
    return jsonify(stream_on=s)


@bp.route("/detect/toggle", methods=["POST"])
def detect_toggle():
    with state._detect_lock:
        state._detect_on = not state._detect_on
        s = state._detect_on
    database.set_setting("detect_on", "true" if s else "false")
    return jsonify(enabled=s)


@bp.route("/detect/category/toggle", methods=["POST"])
def detect_category_toggle():
    cat = (request.get_json(force=True, silent=True) or {}).get("cat", "")
    with state._cat_lock:
        if cat == "person":
            state._cat_person  = not state._cat_person;  s = state._cat_person
        elif cat == "vehicle":
            state._cat_vehicle = not state._cat_vehicle; s = state._cat_vehicle
        elif cat == "other":
            state._cat_other   = not state._cat_other;   s = state._cat_other
        else:
            return jsonify(error="unknown category"), 400
    database.set_setting(f"cat_{cat}", "true" if s else "false")
    return jsonify(cat=cat, enabled=s)


@bp.route("/overlay/toggle/boxes", methods=["POST"])
def overlay_toggle_boxes():
    with state._overlay_lock:
        state._show_boxes = not state._show_boxes
        s = state._show_boxes
    database.set_setting("show_boxes", "true" if s else "false")
    return jsonify(enabled=s)


@bp.route("/overlay/toggle/names", methods=["POST"])
def overlay_toggle_names():
    with state._overlay_lock:
        state._show_names = not state._show_names
        s = state._show_names
    database.set_setting("show_names", "true" if s else "false")
    return jsonify(enabled=s)

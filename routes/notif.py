from datetime import datetime

from flask import Blueprint, jsonify, request

import state
import database
import telegram
from config import NOTIF_HISTORY_MAX

bp = Blueprint("notif", __name__)


@bp.route("/notif/settings", methods=["GET", "POST"])
def notif_settings_route():
    if request.method == "GET":
        with state._notif_lock:
            return jsonify(dict(state._notif_settings))

    data = request.get_json(force=True, silent=True) or {}
    with state._notif_lock:
        if "interval"   in data: state._notif_settings["interval"]   = max(60, int(data["interval"]))
        if "always_on"  in data: state._notif_settings["always_on"]  = bool(data["always_on"])
        if "time_start" in data: state._notif_settings["time_start"] = str(data["time_start"])[:5]
        if "time_end"   in data: state._notif_settings["time_end"]   = str(data["time_end"])[:5]
        if "send_photo" in data: state._notif_settings["send_photo"] = bool(data["send_photo"])
        if "send_video" in data: state._notif_settings["send_video"] = bool(data["send_video"])
        snap = dict(state._notif_settings)
    database.save_notif_settings(snap)
    return jsonify(ok=True, **snap)


@bp.route("/notif/history", methods=["GET"])
def notif_history_all():
    return jsonify(database.load_notif_history(limit=NOTIF_HISTORY_MAX))


@bp.route("/notif/test", methods=["POST"])
def notif_test():
    dt = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    ok, msg = telegram.send_message(
        f"✅ *Tes notifikasi Kamera CW300*\nKonfigurasi berhasil\n🕐 {dt}"
    )
    return jsonify(ok=ok, message=msg)

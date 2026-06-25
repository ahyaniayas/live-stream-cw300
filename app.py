"""
Live Stream + Deteksi Objek — Xiaomi CW300
===========================================
Jalankan:
    pip install -r requirements.txt
    python app.py
Buka: http://localhost:3001
"""
import os
import time
from datetime import datetime
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;+discardcorrupt"

from config import reload_dotenv, log, APP_DEBUG, NOTIF_HISTORY_DISPLAY
reload_dotenv()

import database
import state
import telegram

from flask import Flask

app = Flask(__name__)

# ── Init saat startup ────────────────────────────────────────
database.init_db()
state._zones = database.load_zones()
state._notif_settings.update(database.load_notif_settings())
state._notif_history = database.load_notif_history(limit=NOTIF_HISTORY_DISPLAY)

_app = database.load_app_settings()
state._detect_on   = _app["detect_on"]
state._show_boxes  = _app["show_boxes"]
state._show_names  = _app["show_names"]
state._cat_person  = _app["cat_person"]
state._cat_vehicle = _app["cat_vehicle"]
state._cat_other   = _app["cat_other"]

log(f"Loaded {len(state._zones)} zona, {len(state._notif_history)} riwayat notif dari DB")

# Restore last_notif per zona dari riwayat DB agar cooldown akurat setelah restart
_now_mono = time.monotonic()
_now_wall = datetime.now()
for _entry in state._notif_history:
    try:
        _sent = datetime.strptime(_entry["time"], "%d/%m/%Y %H:%M:%S")
        _ago  = (_now_wall - _sent).total_seconds()
        for _z in state._zones.values():
            if _z["name"] == _entry["zone"] and _z["last_notif"] == 0.0:
                _z["last_notif"] = _now_mono - _ago
    except Exception:
        pass

telegram.start_worker()

import detection
detection.ensure_started()

# ── Daftarkan blueprint ──────────────────────────────────────
from routes import stream_bp, zones_bp, notif_bp
app.register_blueprint(stream_bp)
app.register_blueprint(zones_bp)
app.register_blueprint(notif_bp)


if __name__ == "__main__":
    from config import APP_PORT
    app.run(host="0.0.0.0", port=APP_PORT, threaded=True,
            debug=APP_DEBUG, use_reloader=False)

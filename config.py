import os

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(BASE_DIR, ".env")


def reload_dotenv():
    if not os.path.exists(_ENV_PATH):
        return
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()


reload_dotenv()


def _bool(key, default):
    return os.environ.get(key, str(default)).lower() in ("1", "true", "yes")


def _int(key, default):
    try:
        return int(os.environ.get(key, default))
    except ValueError:
        return default


def _float(key, default):
    try:
        return float(os.environ.get(key, default))
    except ValueError:
        return default


def _str(key, default=""):
    return os.environ.get(key, default)


# ── Dibaca saat import ────────────────────────────────────────
APP_DEBUG      = _bool ("APP_DEBUG",          True)
APP_PORT       = _int  ("APP_PORT",           3001)

STREAM_URL     = _str  ("STREAM_URL",         "rtsp://localhost:8554/cctv")
DETECT_CONF    = _float("DETECT_CONF",        0.35)
DETECT_MAX_FPS = _int  ("DETECT_MAX_FPS",     5)
DETECT_IMGSZ   = _int  ("DETECT_IMGSZ",       640)   # resolusi inference YOLO (bukan sumber)
STREAM_MAX_FPS = _int  ("STREAM_MAX_FPS",     15)
STREAM_WIDTH   = _int  ("STREAM_WIDTH",       1280)  # lebar MJPEG ke browser (0 = asli)

# Path model dibangun dari BASE_DIR/models/<nama file>
YOLO_MODEL     = os.path.join(BASE_DIR, "models",
                               _str("YOLO_MODEL", "yolo11x.pt"))

GATE_ALERT_COOLDOWN = _int("GATE_ALERT_COOLDOWN", 10)
GATE_DEACTIVATE_SEC = _int("GATE_DEACTIVATE_SEC", 3)

NOTIF_HISTORY_DISPLAY = _int ("NOTIF_HISTORY_DISPLAY", 5)
NOTIF_HISTORY_MAX     = _int ("NOTIF_HISTORY_MAX",     100)
NOTIF_SEND_PHOTO      = _bool("NOTIF_SEND_PHOTO",      True)
NOTIF_SEND_VIDEO      = _bool("NOTIF_SEND_VIDEO",      False)
NOTIF_VIDEO_DURATION  = _int ("NOTIF_VIDEO_DURATION",  10)
NOTIF_VIDEO_FPS       = _int ("NOTIF_VIDEO_FPS",       5)

# Telegram — selalu dibaca ulang dari env (tidak di-cache)
def tg_token(): return _str("TELEGRAM_BOT_TOKEN")
def tg_chat():  return _str("TELEGRAM_CHAT_ID")

# ── Konstanta kode (tidak perlu di .env) ─────────────────────
GATE_TARGET_LABELS = {"person"}

COCO_VEHICLES = {
    "bicycle", "car", "motorcycle", "airplane",
    "bus", "train", "truck", "boat",
}

ZONE_PALETTE = [
    (50,  200,  0),
    (0,   165, 255),
    (255,  50, 200),
    (255, 200,   0),
    (200,   0, 255),
]

DB_PATH = os.path.join(BASE_DIR, "cctv_detect.db")

RECORD_DIR = _str("RECORD_DIR", os.path.join(BASE_DIR, "recordings"))


# ── Helpers ───────────────────────────────────────────────────
def label_category(label):
    if label == "person":
        return "person"
    if label in COCO_VEHICLES:
        return "vehicle"
    return "other"


def zone_color(zone_id, is_alert=False):
    if is_alert:
        return (0, 0, 220)
    return ZONE_PALETTE[zone_id % len(ZONE_PALETTE)]


def log(msg):
    if APP_DEBUG:
        print(f"[DEBUG] {msg}", flush=True)

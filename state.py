"""Shared mutable state — diimpor oleh semua modul lain."""
import queue
import threading

# Deteksi
_detect_on        = True
_detect_lock      = threading.Lock()
_last_dets        = []
_last_boxes       = []   # [(x1,y1,x2,y2,label,conf,in_zone), ...] hasil deteksi terakhir
_last_boxes_lock  = threading.Lock()
_stream_fps       = 0.0

# Overlay
_show_boxes   = True
_show_names   = True
_overlay_lock = threading.Lock()

# Kategori
_cat_person  = True
_cat_vehicle = True
_cat_other   = True
_cat_lock    = threading.Lock()

# Zona (diisi dari DB saat startup)
_zones      = {}
_zones_lock = threading.Lock()

# Notifikasi
_notif_settings = {
    "interval":   300,
    "time_start": "00:00",
    "time_end":   "23:59",
    "always_on":  False,
}
_notif_lock:    threading.Lock         = threading.Lock()
_notif_queue:   queue.Queue            = queue.Queue(maxsize=20)
_notif_history: list                   = []

# Instance runtime (di-set oleh detection.py)
_grabber   = None
_detector  = None
_init_lock = threading.Lock()

# YOLO model
_model      = None
_model_lock = threading.Lock()

"""Kirim notifikasi Telegram + worker thread."""
import threading
import urllib.parse
import urllib.request
from datetime import datetime

import cv2

import state
import database
from config import NOTIF_HISTORY_DISPLAY
from config import reload_dotenv, tg_token, tg_chat, log


def is_configured():
    return bool(tg_token() and tg_chat())


def is_in_time_window():
    with state._notif_lock:
        if state._notif_settings.get("always_on", False):
            return True
        t_start = state._notif_settings["time_start"]
        t_end   = state._notif_settings["time_end"]
    now_str = datetime.now().strftime("%H:%M")
    if t_start <= t_end:
        return t_start <= now_str <= t_end
    return now_str >= t_start or now_str <= t_end


def send_photo(caption, frame):
    reload_dotenv()
    token = tg_token()
    chat  = tg_chat()
    if not (token and chat):
        log("Telegram: token/chat_id belum dikonfigurasi di .env")
        return
    try:
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ok:
            return
        img_bytes = buf.tobytes()
        boundary  = b"TGBound1"

        def _field(name, value):
            return (b"--" + boundary + b"\r\n"
                    b'Content-Disposition: form-data; name="' + name.encode() + b'"\r\n\r\n'
                    + value.encode("utf-8") + b"\r\n")

        body = (
            _field("chat_id",     chat)
            + _field("caption",   caption)
            + _field("parse_mode", "Markdown")
            + b"--" + boundary + b"\r\n"
            + b'Content-Disposition: form-data; name="photo"; filename="alert.jpg"\r\n'
            + b"Content-Type: image/jpeg\r\n\r\n"
            + img_bytes + b"\r\n"
            + b"--" + boundary + b"--\r\n"
        )
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary.decode()}"},
        )
        urllib.request.urlopen(req, timeout=10)
        log(f"Telegram: foto terkirim — {caption[:60]}")
    except Exception as exc:
        log(f"Telegram error: {exc}")


def send_message(text):
    reload_dotenv()
    token = tg_token()
    chat  = tg_chat()
    if not (token and chat):
        return False, "Token/chat_id belum dikonfigurasi di .env"
    try:
        data = urllib.parse.urlencode({
            "chat_id":    chat,
            "text":       text,
            "parse_mode": "Markdown",
        }).encode()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        urllib.request.urlopen(url, data, timeout=8)
        return True, "OK"
    except Exception as exc:
        return False, str(exc)


def _worker():
    while True:
        item = state._notif_queue.get()
        if item is None:
            break
        zone_name, count, frame = item
        dt      = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        caption = f"🚨 *Orang terdeteksi di {zone_name}*\n👤 {count} orang\n🕐 {dt}"
        if frame is not None:
            send_photo(caption, frame)
        else:
            send_message(caption)
        database.insert_notif_history(zone_name, count, dt)
        with state._notif_lock:
            state._notif_history.insert(0, {"zone": zone_name, "count": count, "time": dt})
            del state._notif_history[NOTIF_HISTORY_DISPLAY:]
        state._notif_queue.task_done()


def start_worker():
    threading.Thread(target=_worker, daemon=True, name="notif-worker").start()

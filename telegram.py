"""Kirim notifikasi Telegram + worker thread."""
import json
import os
import tempfile
import time
import threading
import urllib.parse
import urllib.request
from datetime import datetime

import cv2

import state
import database
from config import NOTIF_HISTORY_DISPLAY, NOTIF_VIDEO_FPS, NOTIF_VIDEO_DURATION
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _encode_video_bytes(frames):
    if not frames:
        log("Video encode: buffer kosong, skip")
        return None
    fd, tmpfile = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        h, w    = frames[0].shape[:2]
        fourcc  = cv2.VideoWriter_fourcc(*"mp4v")
        writer  = cv2.VideoWriter(tmpfile, fourcc, float(NOTIF_VIDEO_FPS), (w, h))
        if not writer.isOpened():
            log("Video encode: VideoWriter gagal dibuka (codec mp4v tidak tersedia?)")
            return None
        for f in frames:
            writer.write(f)
        writer.release()
        size = os.path.getsize(tmpfile)
        log(f"Video encode: {len(frames)} frame → {size} bytes")
        if size == 0:
            return None
        with open(tmpfile, "rb") as fh:
            return fh.read()
    except Exception as exc:
        log(f"Video encode error: {exc}")
        return None
    finally:
        if os.path.exists(tmpfile):
            os.unlink(tmpfile)


def _multipart_field(boundary, name, value):
    return (b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="' + name.encode() + b'"\r\n\r\n'
            + value.encode("utf-8") + b"\r\n")


def _multipart_file(boundary, name, filename, content_type, data):
    return (b"--" + boundary + b"\r\n"
            + f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
            + f"Content-Type: {content_type}\r\n\r\n".encode()
            + data + b"\r\n")


# ── Kirim tunggal (dipakai oleh tes kirim) ───────────────────────────────────

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
        bd   = b"TGBound1"
        body = (
            _multipart_field(bd, "chat_id",     chat)
            + _multipart_field(bd, "caption",   caption)
            + _multipart_field(bd, "parse_mode", "Markdown")
            + _multipart_file(bd, "photo", "alert.jpg", "image/jpeg", buf.tobytes())
            + b"--" + bd + b"--\r\n"
        )
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        req = urllib.request.Request(url, data=body,
              headers={"Content-Type": f"multipart/form-data; boundary={bd.decode()}"})
        urllib.request.urlopen(req, timeout=15)
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


# ── Media group (foto + video dalam 1 pesan) ─────────────────────────────────

def send_media_group(caption, photo_frames, video_frames=None):
    """Kirim foto dan/atau video sebagai satu pesan media group."""
    reload_dotenv()
    token = tg_token()
    chat  = tg_chat()
    if not (token and chat):
        return

    media_list = []
    file_parts = []   # (key, filename, content_type, bytes)

    # Encode foto
    for i, frame in enumerate(photo_frames):
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ok:
            continue
        key  = f"photo{i}"
        item = {"type": "photo", "media": f"attach://{key}"}
        if not media_list:
            item["caption"]    = caption
            item["parse_mode"] = "Markdown"
        media_list.append(item)
        file_parts.append((key, f"{key}.jpg", "image/jpeg", buf.tobytes()))

    # Encode video
    if video_frames:
        video_bytes = _encode_video_bytes(video_frames)
        if video_bytes:
            key  = "video0"
            item = {"type": "video", "media": f"attach://{key}"}
            if not media_list:
                item["caption"]    = caption
                item["parse_mode"] = "Markdown"
            media_list.append(item)
            file_parts.append((key, "clip.mp4", "video/mp4", video_bytes))

    if not media_list:
        send_message(caption)
        return

    # Fallback ke sendPhoto jika hanya 1 foto
    if len(media_list) == 1 and media_list[0]["type"] == "photo":
        send_photo(caption, photo_frames[0])
        return

    # sendMediaGroup
    bd   = b"TGBound3"
    body = (_multipart_field(bd, "chat_id", chat)
            + _multipart_field(bd, "media", json.dumps(media_list)))
    for key, filename, ct, data in file_parts:
        body += _multipart_file(bd, key, filename, ct, data)
    body += b"--" + bd + b"--\r\n"

    log(f"sendMediaGroup: {[m['type'] for m in media_list]}")
    try:
        url = f"https://api.telegram.org/bot{token}/sendMediaGroup"
        req = urllib.request.Request(url, data=body,
              headers={"Content-Type": f"multipart/form-data; boundary={bd.decode()}"})
        urllib.request.urlopen(req, timeout=60)
        log(f"Telegram: media group terkirim ({len(media_list)} item) — {caption[:50]}")
    except Exception as exc:
        log(f"Telegram media group error: {exc}")


# ── Worker ────────────────────────────────────────────────────────────────────

def _collect_photos(first_frame, count=5, interval=1.0):
    """Kumpulkan `count` foto dengan jeda `interval` detik antar frame."""
    photos = [first_frame] if first_frame is not None else []
    for _ in range(count - 1):
        time.sleep(interval)
        f = state._grabber.read() if state._grabber else None
        if f is not None:
            photos.append(f)
    return photos


def _collect_video_frames():
    """Kumpulkan frame video selama NOTIF_VIDEO_DURATION detik sejak objek terdeteksi."""
    n        = NOTIF_VIDEO_FPS * NOTIF_VIDEO_DURATION
    interval = 1.0 / max(1, NOTIF_VIDEO_FPS)
    frames   = []
    for _ in range(n):
        t = time.monotonic()
        f = state._grabber.read() if state._grabber else None
        if f is not None:
            frames.append(f)
        wait = interval - (time.monotonic() - t)
        if wait > 0:
            time.sleep(wait)
    return frames


def _worker():
    while True:
        item = state._notif_queue.get()
        if item is None:
            break
        zone_name, count, frame = item
        dt      = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        caption = f"🚨 *Orang terdeteksi di {zone_name}*\n👤 {count} orang\n🕐 {dt}"

        with state._notif_lock:
            do_photo = state._notif_settings.get("send_photo", True)
            do_video = state._notif_settings.get("send_video", False)

        if do_photo and do_video:
            # 1 foto (saat deteksi) + video 10 detik setelah deteksi → 1 pesan
            photos = [frame] if frame is not None else []
            clip   = _collect_video_frames()
            log(f"Notif foto+video: {len(photos)} foto, {len(clip)} frame")
            send_media_group(caption, photos, clip)

        elif do_photo:
            # Kumpulkan 5 foto (1/detik selama 5 detik) → 1 pesan
            photos = _collect_photos(frame, count=5, interval=1.0)
            send_media_group(caption, photos)

        elif do_video:
            # Video 10 detik setelah deteksi
            clip = _collect_video_frames()
            video_bytes = _encode_video_bytes(clip)
            if video_bytes:
                reload_dotenv()
                _tok  = tg_token()
                _chat = tg_chat()
                if _tok and _chat:
                    bd   = b"TGBound2"
                    body = (
                        _multipart_field(bd, "chat_id",     _chat)
                        + _multipart_field(bd, "caption",   caption)
                        + _multipart_field(bd, "parse_mode", "Markdown")
                        + _multipart_file(bd, "video", "clip.mp4", "video/mp4", video_bytes)
                        + b"--" + bd + b"--\r\n"
                    )
                    try:
                        url = f"https://api.telegram.org/bot{_tok}/sendVideo"
                        req = urllib.request.Request(url, data=body,
                              headers={"Content-Type": f"multipart/form-data; boundary={bd.decode()}"})
                        urllib.request.urlopen(req, timeout=60)
                        log(f"Telegram: video terkirim — {caption[:60]}")
                    except Exception as exc:
                        log(f"Telegram video error: {exc}")
            else:
                send_message(caption)

        else:
            send_message(caption)

        database.insert_notif_history(zone_name, count, dt)
        with state._notif_lock:
            state._notif_history.insert(0, {"zone": zone_name, "count": count, "time": dt})
            del state._notif_history[NOTIF_HISTORY_DISPLAY:]
        state._notif_queue.task_done()


def start_worker():
    threading.Thread(target=_worker, daemon=True, name="notif-worker").start()

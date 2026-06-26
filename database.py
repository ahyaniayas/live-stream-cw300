"""Semua operasi database — cctv_detect.db."""
import json
import os
import sqlite3

from config import DB_PATH, NOTIF_HISTORY_MAX, log


def _conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS zones (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                points      TEXT    NOT NULL DEFAULT '[]',
                total_count INTEGER NOT NULL DEFAULT 0,
                notify      INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT    DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notif_history (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                zone    TEXT NOT NULL,
                count   INTEGER NOT NULL,
                sent_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        # Seed default — hanya jika key belum ada (INSERT OR IGNORE)
        defaults = {
            # Deteksi
            "detect_on":        "true",
            "show_boxes":       "true",
            "show_names":       "true",
            "cat_person":       "true",
            "cat_vehicle":      "true",
            "cat_other":        "true",
            # Notifikasi — default dari .env
            "notif_interval":   os.environ.get("NOTIF_INTERVAL",    "300"),
            "notif_always_on":  os.environ.get("NOTIF_ALWAYS_ON",  "false"),
            "notif_time_start": os.environ.get("NOTIF_TIME_START", "00:00"),
            "notif_time_end":   os.environ.get("NOTIF_TIME_END",   "23:59"),
            "notif_send_photo": os.environ.get("NOTIF_SEND_PHOTO", "true"),
            "notif_send_video": os.environ.get("NOTIF_SEND_VIDEO", "false"),
        }
        for k, v in defaults.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        conn.commit()
    log(f"DB siap: {DB_PATH}")


# ── Zona ──────────────────────────────────────────────────────

def zone_runtime(zid, name, points, total_count=0, notify=False):
    return {
        "id":            zid,
        "name":          name,
        "points":        points,
        "active":        False,
        "last_trigger":  0.0,
        "last_seen":     0.0,
        "last_notif":    0.0,
        "total_count":   total_count,
        "current_count": 0,
        "notify":        notify,
    }


def load_zones():
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM zones ORDER BY id").fetchall()
    return {
        r["id"]: zone_runtime(
            r["id"], r["name"], json.loads(r["points"]),
            r["total_count"], bool(r["notify"]),
        )
        for r in rows
    }


def insert_zone(name, points_json):
    with _conn() as conn:
        cur = conn.execute("INSERT INTO zones (name, points) VALUES (?, ?)",
                           (name, points_json))
        conn.commit()
        return cur.lastrowid


def update_zone(zone_id, name=None, points_json=None):
    with _conn() as conn:
        if name:
            conn.execute("UPDATE zones SET name=? WHERE id=?", (name, zone_id))
        if points_json is not None:
            conn.execute("UPDATE zones SET points=? WHERE id=?", (points_json, zone_id))
        conn.commit()


def delete_zone(zone_id):
    with _conn() as conn:
        conn.execute("DELETE FROM zones WHERE id=?", (zone_id,))
        conn.commit()


def upsert_zone_count(zone_id, count):
    with _conn() as conn:
        conn.execute("UPDATE zones SET total_count=? WHERE id=?", (count, zone_id))
        conn.commit()


def upsert_zone_notify(zone_id, notify):
    with _conn() as conn:
        conn.execute("UPDATE zones SET notify=? WHERE id=?", (int(notify), zone_id))
        conn.commit()


# ── Pengaturan ────────────────────────────────────────────────

def _get_setting(key, default=""):
    with _conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def _set_setting(key, value):
    with _conn() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                     (key, str(value)))
        conn.commit()


def _bool_val(key, default="true"):
    return _get_setting(key, default).lower() in ("1", "true", "yes")


def set_setting(key, value):
    _set_setting(key, value)


def load_app_settings():
    return {
        "detect_on":  _bool_val("detect_on",  "true"),
        "show_boxes": _bool_val("show_boxes",  "true"),
        "show_names": _bool_val("show_names",  "true"),
        "cat_person": _bool_val("cat_person",  "true"),
        "cat_vehicle":_bool_val("cat_vehicle", "true"),
        "cat_other":  _bool_val("cat_other",   "true"),
    }


def load_notif_settings():
    def _b(key, default):
        return _get_setting(key, default).lower() in ("1", "true", "yes")
    return {
        "interval":   int(_get_setting("notif_interval",   "300")),
        "always_on":  _b("notif_always_on",  "false"),
        "time_start": _get_setting("notif_time_start", "00:00"),
        "time_end":   _get_setting("notif_time_end",   "23:59"),
        "send_photo": _b("notif_send_photo", "true"),
        "send_video": _b("notif_send_video", "false"),
    }


def save_notif_settings(d):
    if "interval"   in d: _set_setting("notif_interval",   d["interval"])
    if "always_on"  in d: _set_setting("notif_always_on",  "true" if d["always_on"]  else "false")
    if "time_start" in d: _set_setting("notif_time_start", d["time_start"])
    if "time_end"   in d: _set_setting("notif_time_end",   d["time_end"])
    if "send_photo" in d: _set_setting("notif_send_photo", "true" if d["send_photo"] else "false")
    if "send_video" in d: _set_setting("notif_send_video", "true" if d["send_video"] else "false")


# ── Riwayat Notifikasi ────────────────────────────────────────

def insert_notif_history(zone, count, sent_at):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO notif_history (zone, count, sent_at) VALUES (?, ?, ?)",
            (zone, count, sent_at),
        )
        conn.execute(
            "DELETE FROM notif_history WHERE id NOT IN "
            "(SELECT id FROM notif_history ORDER BY id DESC LIMIT ?)",
            (NOTIF_HISTORY_MAX,),
        )
        conn.commit()


def load_notif_history(limit=5):
    with _conn() as conn:
        rows = conn.execute(
            "SELECT zone, count, sent_at FROM notif_history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [{"zone": r["zone"], "count": r["count"], "time": r["sent_at"]} for r in rows]

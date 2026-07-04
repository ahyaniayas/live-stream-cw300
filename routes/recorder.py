import time
from pathlib import Path

from flask import Blueprint, Response, abort, jsonify, render_template, request, send_file

from config import RECORD_DIR

bp = Blueprint("recorder", __name__)

_RECORD_PATH = Path(RECORD_DIR) / "2k"

# File dianggap masih direkam jika mtime < N detik yang lalu
_RECORDING_THRESHOLD = 30


def _list_files():
    if not _RECORD_PATH.exists():
        return []
    now = time.time()
    files = sorted(_RECORD_PATH.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in files:
        stat = f.stat()
        result.append({
            "name": f.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "recording": (now - stat.st_mtime) < _RECORDING_THRESHOLD,
        })
    return result


def _serve_range(path: Path):
    # Gunakan fitur bawaan Flask (Werkzeug) untuk menangani HTTP Range Request.
    # Flask secara otomatis akan menangani byte-range (termasuk suffix bytes, If-Range, dll)
    # yang sangat dibutuhkan oleh Firefox untuk memparsing durasi video dengan benar.
    return send_file(path, mimetype="video/mp4", conditional=True)


@bp.route("/recordings")
def recordings_page():
    return render_template("recordings.html")


@bp.route("/recordings/list")
def recordings_list():
    files = _list_files()
    total = sum(f["size"] for f in files)
    return jsonify(files=files, total_size=total)


@bp.route("/recordings/video/<filename>")
def recordings_video(filename):
    path = _RECORD_PATH / filename
    if not path.exists() or path.suffix.lower() != ".mp4":
        abort(404)
    return _serve_range(path)


@bp.route("/recordings/delete/<filename>", methods=["DELETE"])
def recordings_delete(filename):
    path = _RECORD_PATH / filename
    if not path.exists() or path.suffix.lower() != ".mp4":
        abort(404)
    path.unlink()
    return jsonify(ok=True)

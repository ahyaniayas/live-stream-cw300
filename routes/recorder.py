import os
import subprocess
from pathlib import Path

from flask import Blueprint, Response, abort, jsonify, render_template, request, send_file

from config import RECORD_DIR

bp = Blueprint("recorder", __name__)

_RECORD_PATH = Path(RECORD_DIR) / "2k"


def _list_files():
    if not _RECORD_PATH.exists():
        return []
    files = sorted(_RECORD_PATH.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in files:
        stat = f.stat()
        result.append({
            "name": f.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        })
    return result


def _serve_range(path: Path):
    file_size = path.stat().st_size
    range_header = request.headers.get("Range")

    if range_header and range_header.startswith("bytes="):
        parts = range_header[6:].split("-")
        byte_start = int(parts[0]) if parts[0] else 0
        byte_end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        byte_end = min(byte_end, file_size - 1)
        length = byte_end - byte_start + 1

        def _generate():
            with open(path, "rb") as fh:
                fh.seek(byte_start)
                remaining = length
                while remaining > 0:
                    chunk = fh.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return Response(
            _generate(),
            status=206,
            mimetype="video/mp4",
            headers={
                "Content-Range": f"bytes {byte_start}-{byte_end}/{file_size}",
                "Content-Length": str(length),
                "Accept-Ranges": "bytes",
            },
        )

    resp = send_file(path, mimetype="video/mp4")
    resp.headers["Accept-Ranges"] = "bytes"
    resp.headers["Content-Length"] = str(file_size)
    return resp


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


@bp.route("/recordings/stream/<filename>")
def recordings_stream(filename):
    """Transcode HEVC → H.264 on-the-fly sehingga bisa diputar di semua browser."""
    path = _RECORD_PATH / filename
    if not path.exists() or path.suffix.lower() != ".mp4":
        abort(404)

    cmd = [
        "ffmpeg", "-i", str(path),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac",
        "-f", "mp4",
        "-movflags", "frag_keyframe+empty_moov",
        "pipe:1",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def _generate():
        try:
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            proc.kill()
            proc.wait()

    return Response(
        _generate(),
        mimetype="video/mp4",
        headers={"X-Accel-Buffering": "no"},
    )


@bp.route("/recordings/delete/<filename>", methods=["DELETE"])
def recordings_delete(filename):
    path = _RECORD_PATH / filename
    if not path.exists() or path.suffix.lower() != ".mp4":
        abort(404)
    path.unlink()
    return jsonify(ok=True)

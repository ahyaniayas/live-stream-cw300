#!/usr/bin/env python3
"""
Hapus file rekaman terlama jika total ukuran 2K melebihi batas.
Dijalankan via systemd timer tiap 5 menit.
"""
import os
import sys
from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _load_dotenv():
    if not _ENV_PATH.exists():
        return
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()


_load_dotenv()

RECORD_DIR  = Path(os.environ.get("RECORD_DIR",      "/home/serverku/live-stream-cw300/recordings"))
MAX_BYTES   = int(os.environ.get("RECORD_MAX_GB",    "16")) * 1024 ** 3


def all_files():
    files = []
    folder = RECORD_DIR / "2k"
    if folder.exists():
        files.extend(folder.glob("*.mp4"))
    return sorted(files, key=lambda f: f.stat().st_mtime)


def total_size(files):
    return sum(f.stat().st_size for f in files if f.exists())


def main():
    files     = all_files()
    size      = total_size(files)
    max_gb    = MAX_BYTES / 1024 ** 3
    print(f"Rekaman: {size / 1024**3:.2f} GB / {max_gb:.0f} GB ({len(files)} file)")

    deleted = 0
    while size > MAX_BYTES and files:
        oldest    = files.pop(0)
        file_size = oldest.stat().st_size
        oldest.unlink()
        size    -= file_size
        deleted += 1
        print(f"Hapus: {oldest.relative_to(RECORD_DIR)} ({file_size / 1024**2:.1f} MB)")

    if deleted:
        print(f"Selesai: {deleted} file dihapus, sisa {size / 1024**3:.2f} GB")
    else:
        print("OK: ukuran dalam batas")


if __name__ == "__main__":
    main()

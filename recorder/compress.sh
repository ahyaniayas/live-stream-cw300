#!/bin/bash
# Kompres ulang rekaman lama (HEVC) pakai preset software encoder yang lebih efisien
# supaya ukuran file lebih kecil dengan kualitas visual setara.
# Didesain untuk dijalankan via cron di jam sepi, mis. tiap malam jam 03:00:
#   0 3 * * * /home/serverku/live-stream-cw300/recorder/compress.sh >> /home/serverku/live-stream-cw300/recorder/compress.log 2>&1
#
# File yang sudah pernah dikompres ditandai lewat metadata "comment" di dalam MP4-nya
# sendiri, jadi run berikutnya otomatis skip file yang sama.

set -u

ENV_FILE="$(dirname "$0")/../.env"
RECORD_DIR="$(grep -E '^RECORD_DIR='     "$ENV_FILE" 2>/dev/null | cut -d= -f2-)"
CRF="$(grep -E '^COMPRESS_CRF='         "$ENV_FILE" 2>/dev/null | cut -d= -f2-)"
PRESET="$(grep -E '^COMPRESS_PRESET='   "$ENV_FILE" 2>/dev/null | cut -d= -f2-)"
THREADS="$(grep -E '^COMPRESS_THREADS=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)"

RECORD_DIR="${RECORD_DIR:-/home/serverku/live-stream-cw300/recordings}"
CRF="${CRF:-27}"
PRESET="${PRESET:-slow}"
THREADS="${THREADS:-2}"
DIR="$RECORD_DIR/2k"

MIN_AGE_SEC=120        # jangan sentuh file yang mungkin masih ditulis ffmpeg
TAG="compressed_v1"    # penanda di metadata "comment" file yang sudah dikompres

LOCK="/tmp/cw300_compress.lock"
exec 9>"$LOCK"
flock -n 9 || { echo "$(date '+%F %T') Proses compress lain masih jalan, skip run ini."; exit 0; }

_stat_mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null; }
_stat_size()  { stat -c %s "$1" 2>/dev/null || stat -f %z "$1" 2>/dev/null; }

echo "$(date '+%F %T') === Mulai compress run (crf=$CRF preset=$PRESET) ==="

now=$(date +%s)
shopt -s nullglob
for f in "$DIR"/*.mp4; do
    name="$(basename "$f")"

    mtime=$(_stat_mtime "$f")
    age=$(( now - mtime ))
    if (( age < MIN_AGE_SEC )); then
        continue
    fi

    tag=$(ffprobe -v error -show_entries format_tags=comment \
            -of default=noprint_wrappers=1:nokey=1 "$f" 2>/dev/null)
    if [[ "$tag" == "$TAG" ]]; then
        continue
    fi

    echo "$(date '+%F %T') Compress: $name"
    tmp="$DIR/.tmp_${name}"

    nice -n 19 ionice -c3 ffmpeg -y -i "$f" \
        -c:v libx265 -preset "$PRESET" -crf "$CRF" -tag:v hvc1 -threads "$THREADS" \
        -c:a copy \
        -metadata comment="$TAG" \
        -movflags +faststart \
        "$tmp" </dev/null >/dev/null 2>&1
    status=$?

    if [[ $status -eq 0 && -s "$tmp" ]]; then
        if [[ ! -e "$f" ]]; then
            echo "$(date '+%F %T') Dilewati: $name sudah dihapus watchdog selagi dikompres."
            rm -f "$tmp"
            continue
        fi
        touch -r "$f" "$tmp"   # pertahankan mtime asli, biar urutan hapus watchdog tetap benar
        old_size=$(_stat_size "$f")
        new_size=$(_stat_size "$tmp")
        mv -f "$tmp" "$f"
        echo "$(date '+%F %T') OK: $name ($old_size -> $new_size bytes)"
    else
        echo "$(date '+%F %T') GAGAL (exit=$status): $name, file asli tidak diubah."
        rm -f "$tmp"
    fi
done

echo "$(date '+%F %T') === Selesai ==="

#!/bin/bash
# Rekam stream 2K menggunakan ffmpeg.
# Segmen 15 menit, format MP4, stream copy (tanpa re-encode).
# Edit variabel di bawah sesuai server kamu.

ENV_FILE="$(dirname "$0")/../.env"
RECORD_DIR="$(grep -E '^RECORD_DIR=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)"
RECORD_DIR="${RECORD_DIR:-/home/serverku/live-stream-cw300/recordings}"
SEGMENT_SEC=900
RTSP_2K="rtsp://localhost:8554/cctv_sub3"

mkdir -p "$RECORD_DIR/2k"

INPUT_ARGS="-rtsp_transport tcp -fflags +genpts -use_wallclock_as_timestamps 1"
FFMPEG_ARGS="-c:v copy -tag:v hvc1 -c:a aac -b:a 128k -f segment -segment_time $SEGMENT_SEC -segment_atclocktime 1 -segment_format mp4 -strftime 1 -reset_timestamps 1 -movflags +faststart"

ffmpeg $INPUT_ARGS -i "$RTSP_2K" $FFMPEG_ARGS "$RECORD_DIR/2k/%Y%m%d_%H%M%S.mp4" &
PID_2K=$!

# Saat service dihentikan (SIGTERM), hentikan ffmpeg
trap "kill $PID_2K 2>/dev/null; exit 0" SIGTERM SIGINT

wait $PID_2K

#!/bin/bash
# Rekam stream 2K menggunakan ffmpeg.
# Segmen 15 menit, format MP4, stream copy (tanpa re-encode).
# Edit variabel di bawah sesuai server kamu.

RECORD_DIR="/home/serverku/live-stream-cw300/recordings"
SEGMENT_SEC=300   # 5 menit
RTSP_2K="rtsp://localhost:8554/cctv_sub3"

mkdir -p "$RECORD_DIR/2k"

FFMPEG_ARGS="-rtsp_transport tcp -c copy -f segment -segment_time $SEGMENT_SEC -segment_atclocktime 1 -segment_format mp4 -strftime 1 -reset_timestamps 1 -movflags +faststart"

ffmpeg -i "$RTSP_2K" $FFMPEG_ARGS "$RECORD_DIR/2k/%Y%m%d_%H%M%S.mp4" &
PID_2K=$!

# Saat service dihentikan (SIGTERM), hentikan ffmpeg
trap "kill $PID_2K 2>/dev/null; exit 0" SIGTERM SIGINT

wait $PID_2K

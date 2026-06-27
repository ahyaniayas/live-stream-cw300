# CCTV Recorder

Rekam stream 2K dari go2rtc ke file MP4 tersegmentasi dengan batas ukuran otomatis.

## Cara Kerja

```
go2rtc (RTSP) → ffmpeg -c copy → file MP4 (15 menit/segmen)
                                        ↓
                              watchdog (tiap 5 menit)
                              hapus file terlama jika total > batas
```

- **Tanpa re-encode** — ffmpeg hanya menyalin stream HEVC langsung ke MP4 (CPU minimal)
- **2K** → `cctv_sub3` (2560×1440 @ 20fps) disimpan di `2k/`
- Nama file: `20250627_143000.mp4` (format `YYYYMMDD_HHMMSS`)

---

## File

| File | Fungsi |
|------|--------|
| `recorder.sh` | Jalankan ffmpeg rekam stream 2K |
| `recorder.service` | Systemd service untuk `recorder.sh` |
| `watchdog.py` | Hapus file terlama jika total ukuran melebihi batas |
| `watchdog.service` | Systemd service untuk watchdog (oneshot) |
| `watchdog.timer` | Jalankan watchdog tiap 5 menit |
| `install.sh` | Install semua ke systemd |

---

## Konfigurasi

Edit sebelum install:

### `recorder.sh`
```bash
RECORD_DIR="/home/serverku/live-stream-cw300/recordings"  # folder rekaman (di dalam project)
SEGMENT_SEC=900                                            # durasi segmen (detik) — 900 = 15 menit
RTSP_2K="rtsp://localhost:8554/cctv_sub3"
```

### `watchdog.service`
```ini
Environment=RECORD_DIR=/home/serverku/live-stream-cw300/recordings
Environment=RECORD_MAX_GB=64                               # batas ukuran (GB)
ExecStart=/usr/bin/python3 /home/serverku/live-stream-cw300/recorder/watchdog.py
```

### `recorder.service`
```ini
User=serverku                                              # ganti dengan username server
ExecStart=/bin/bash /home/serverku/live-stream-cw300/recorder/recorder.sh
```

---

## Instalasi

```bash
# 1. Edit konfigurasi di recorder.sh, watchdog.service, recorder.service
# 2. Beri permission executable (lakukan sekali setelah git pull)
chmod +x recorder/recorder.sh recorder/install.sh
# 3. Jalankan install (hanya sekali)
sudo bash recorder/install.sh
```

---

## Perintah Harian

### Status

```bash
# Cek semua sekaligus
sudo systemctl status recorder.service watchdog.timer

# Detail recorder
sudo systemctl status recorder.service

# Hasil run watchdog terakhir
sudo systemctl status watchdog.service
```

### Start / Stop / Restart

```bash
# Recorder
sudo systemctl start   recorder.service
sudo systemctl stop    recorder.service
sudo systemctl restart recorder.service

# Watchdog timer
sudo systemctl start   watchdog.timer
sudo systemctl stop    watchdog.timer

# Jalankan watchdog sekarang (manual, tanpa tunggu 5 menit)
sudo systemctl start   watchdog.service
```

### Log Real-time

```bash
# Log recorder (output ffmpeg)
sudo journalctl -u recorder.service -f

# Log watchdog
sudo journalctl -u watchdog.service

# Log keduanya sekaligus
sudo journalctl -u recorder.service -u watchdog.service -f
```

### Nonaktifkan Permanen

```bash
# Berhenti dan tidak auto-start saat reboot
sudo systemctl disable --now recorder.service
sudo systemctl disable --now watchdog.timer
```

---

## Estimasi Ukuran

Berdasarkan bitrate aktual kamera (HEVC, scene statis):

| Stream | Bitrate aktual | Per 15 menit | Per hari |
|--------|---------------|-------------|---------|
| 2K (2560×1440) | ~1.3 Mbps | ~146 MB | ~14 GB |

| Batas (`RECORD_MAX_GB`) | Perkiraan durasi simpan |
|------------------------|------------------------|
| 16 GB | ~1 hari |
| 64 GB | ~4 hari |
| 128 GB | ~9 hari |

> Bitrate HEVC sangat bergantung pada banyaknya gerakan di scene.
> Scene ramai = file lebih besar dari estimasi di atas.

---

## Prasyarat

```bash
# ffmpeg harus terinstall di server
sudo apt install -y ffmpeg

# go2rtc harus berjalan dan stream tersedia
curl http://localhost:1984/api/streams
```

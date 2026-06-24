# Live Stream + Deteksi Objek — Xiaomi CW300

Aplikasi web untuk memantau live stream kamera Xiaomi CW300 dengan deteksi objek real-time menggunakan YOLO11x, zona deteksi multi-area, dan notifikasi Telegram.

## Arsitektur

```
Kamera CW300 (RTSP) ──► go2rtc ──► app.py (Flask/MJPEG) ──► Browser
                                         │
                                      YOLO11x
                                   (deteksi objek)
                                         │
                                    Telegram Bot
                                  (notifikasi zona)
```

| Komponen | Fungsi |
|---|---|
| **go2rtc** | Menjembatani protokol Xiaomi ke RTSP standar |
| **Flask** | Server web + MJPEG stream ke browser |
| **OpenCV** | Baca frame RTSP, encode ke JPEG |
| **YOLO11x** | Deteksi 80 kelas objek COCO |
| **SQLite** | Penyimpanan zona dan pengaturan (`cctv_detect.db`) |
| **Telegram Bot** | Kirim foto alert saat orang terdeteksi di zona |

---

## Prasyarat

- Python 3.10+
- Docker (untuk go2rtc)

## Instalasi

```bash
pip install -r requirements.txt
```

---

## Konfigurasi

### 1. `.env`

Salin dan sesuaikan file `.env`:

```env
# Aplikasi
APP_DEBUG=true
APP_PORT=3001

# Stream RTSP dari go2rtc
STREAM_URL=rtsp://localhost:8554/cctv

# Deteksi
DETECT_CONF=0.35        # threshold confidence (0.0–1.0)
DETECT_MAX_FPS=5        # FPS YOLO
STREAM_MAX_FPS=25       # FPS ke browser
YOLO_MODEL=yolo11x.pt  # nama file di folder models/

# Zona
GATE_ALERT_COOLDOWN=10  # detik antar alert per zona
GATE_DEACTIVATE_SEC=3   # detik sebelum zona dianggap kosong

# Notifikasi (default awal, dapat diubah via UI)
NOTIF_INTERVAL=300      # detik antar notifikasi (300 = 5 menit)
NOTIF_ALWAYS_ON=false   # true = abaikan jam aktif
NOTIF_TIME_START=00:00  # jam mulai kirim notifikasi
NOTIF_TIME_END=23:59    # jam akhir kirim notifikasi

# Telegram
TELEGRAM_BOT_TOKEN=<token dari @BotFather>
TELEGRAM_CHAT_ID=<chat_id tujuan>
```

### 2. go2rtc — Stream Video

Jalankan token extractor untuk mendapatkan kredensial kamera:

```bash
bash <(curl -L https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor/raw/master/run.sh)
```

Salin `did`, `ip`, dan `token` ke `go2rtc/go2rtc.yaml`, lalu jalankan:

```bash
cd go2rtc && docker compose up -d
```

Verifikasi stream di `http://localhost:1984`.

### 3. Telegram Bot

1. Buat bot via [@BotFather](https://t.me/BotFather), salin token ke `.env`
2. Dapatkan `chat_id`:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```
   Kirim pesan ke bot terlebih dahulu agar muncul di hasil `getUpdates`.
3. Isi `TELEGRAM_CHAT_ID` di `.env`

---

## Menjalankan

### go2rtc

```bash
cd go2rtc && docker compose up -d && cd ..
```

### Web App (foreground)

```bash
python app.py
```

### Web App (background dengan systemd)

Buat service file:
```bash
sudo nano /etc/systemd/system/cctv.service
```

Isi:
```ini
[Unit]
Description=CCTV Live Stream Detection
After=network.target

[Service]
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/live-stream-cw300
ExecStart=/home/YOUR_USERNAME/.pyenv/shims/python app.py
Restart=on-failure
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Aktifkan dan jalankan:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cctv
sudo systemctl start cctv
```

Cek status dan log:
```bash
sudo systemctl status cctv
sudo journalctl -u cctv -f        # log realtime
sudo journalctl -u cctv -n 100    # 100 baris terakhir
```

Buka browser: **http://\<IP-SERVER\>:3001**

---

## Fitur

### Stream & Deteksi
- Live stream MJPEG latensi rendah dengan auto-reconnect
- Deteksi 80 kelas objek COCO (YOLO11x) secara real-time
- Toggle deteksi on/off tanpa restart
- Filter kategori: Orang / Kendaraan / Objek Lainnya
- Toggle tampilan kotak dan nama objek

### Zona Deteksi
- Buat zona poligon dengan klik langsung di video
- Deteksi orang masuk zona berdasarkan overlap bounding box (bukan hanya titik tengah)
- Counter orang saat ini dan total per zona
- Alert banner merah saat zona aktif
- Reset counter per zona

### Notifikasi Telegram
- Kirim foto frame saat orang terdeteksi di zona
- Toggle notifikasi per zona (ikon 🔔 di card zona)
- **Selalu Aktif** — kirim notifikasi kapan saja, abaikan jam aktif
- Jam aktif — batasi pengiriman pada rentang waktu tertentu (mendukung lintas tengah malam)
- Interval pengiriman — cegah spam notifikasi
- Cooldown badge real-time: hitung mundur kuning → "Siap" hijau
- Riwayat 5 notifikasi terakhir
- Tombol tes kirim

---

## Struktur Proyek

```
live-stream-cw300/
├── app.py              # Entry point — Flask app + startup
├── config.py           # Konstanta + baca .env
├── state.py            # Shared global state & locks
├── database.py         # Semua DB ops (cctv_detect.db)
├── detection.py        # FrameGrabber, Detector (YOLO), mjpeg_stream
├── zones.py            # Logika zona: bbox check, update, draw
├── telegram.py         # Kirim notifikasi + worker thread
├── routes/
│   ├── stream.py       # /video_feed, /status, /detect/*, /overlay/*
│   ├── zone_api.py     # /zones CRUD
│   └── notif.py        # /notif/settings, /notif/test
├── templates/
│   └── index.html      # HTML UI
├── static/
│   ├── style.css       # Semua CSS
│   └── app.js          # Semua JavaScript
├── models/
│   └── yolo11x.pt      # Model YOLO (dan model lainnya)
├── go2rtc/             # Konfigurasi + binary go2rtc
├── .env                # Konfigurasi (tidak di-commit)
└── cctv_detect.db      # Database SQLite (dibuat otomatis)
```

---

## Database

`cctv_detect.db` dibuat otomatis saat pertama kali `app.py` dijalankan.

| Tabel | Isi |
|---|---|
| `zones` | Nama, titik poligon, counter, flag notifikasi |
| `settings` | Pengaturan notifikasi (interval, jam aktif, selalu aktif) |

Pengaturan default di-seed dari `.env` hanya saat key belum ada di DB (`INSERT OR IGNORE`). Perubahan via UI tersimpan ke DB dan bertahan antar restart.

---

## Troubleshooting

| Gejala | Kemungkinan Penyebab |
|---|---|
| Layar hitam / loader terus | go2rtc belum jalan atau `STREAM_URL` salah |
| FPS rendah | Turunkan `DETECT_MAX_FPS` atau ganti model ke `yolo11l.pt` |
| Banyak false positive | Naikkan `DETECT_CONF` (misal `0.5`) |
| Notifikasi tidak terkirim | Cek token/chat_id di `.env`, pastikan bot sudah pernah dikirimi pesan |
| Zona tidak terdeteksi | Pastikan area zona cukup besar dan orang sepenuhnya masuk frame |

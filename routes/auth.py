"""PIN gate — semua halaman web butuh PIN sebelum bisa diakses.

PIN = 2 digit tanggal + 2 digit jam (format 24 jam) + 2 digit menit.
Contoh: 7 Oktober 14:35 → "071435".

PIN dianggap sah selama PIN_VALID_HOURS terakhir, jadi PIN yang dilihat
beberapa jam lalu masih bisa dipakai. Setelah berhasil masuk, sesi berlaku
PIN_VALID_HOURS tanpa perlu memasukkan PIN lagi.
"""
import time

from flask import (Blueprint, redirect, render_template_string, request,
                   session, url_for)

from config import pin_valid

auth_bp = Blueprint("auth", __name__)

_MAX_FAILS = 8    # percobaan salah berturut-turut sebelum IP diblokir
_BLOCK_SEC = 60
_fails     = {}   # ponytail: in-memory per-IP, cukup untuk LAN


_LOGIN_HTML = """<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Masuk — Kamera CW300</title>
<style>
  :root{--bg:#0f1115;--panel:#1a1d24;--panel2:#22262f;--accent:#ff6900;
        --txt:#e7e9ee;--red:#ef4444;--muted:#6b7280;}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,system-ui,sans-serif;background:var(--bg);
       color:var(--txt);min-height:100vh;display:flex;align-items:center;
       justify-content:center;padding:16px}
  form{background:var(--panel);border-radius:14px;padding:28px 24px;width:100%;
       max-width:340px;display:flex;flex-direction:column;gap:14px;
       box-shadow:0 8px 30px rgba(0,0,0,.45)}
  h1{font-size:17px;font-weight:600;text-align:center}
  .hint{font-size:12px;color:var(--muted);text-align:center;line-height:1.5}
  input{background:var(--panel2);border:1px solid #ffffff14;border-radius:9px;
        color:var(--txt);font-family:inherit;font-size:22px;letter-spacing:6px;
        text-align:center;padding:12px;outline:none;width:100%}
  input:focus{border-color:var(--accent)}
  button{background:var(--accent);border:none;border-radius:9px;color:#fff;
         font-family:inherit;font-size:14px;font-weight:600;padding:11px;
         cursor:pointer}
  button:hover{opacity:.88}
  .err{background:rgba(239,68,68,.15);color:var(--red);font-size:12.5px;
       border-radius:8px;padding:8px 10px;text-align:center}
</style>
</head>
<body>
  <form method="post" action="/login">
    <h1>Kamera Xiaomi CW300</h1>
    <p class="hint">Masukkan PIN 6 digit</p>
    <input name="pin" type="text" inputmode="numeric" pattern="[0-9]{6}"
           maxlength="6" autocomplete="off" autofocus required
           placeholder="XXXXXX"
           oninput="this.value=this.value.replace(/[^0-9]/g,'');
                    if(this.value.length===6) this.form.submit()">
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
    <button type="submit">Masuk</button>
  </form>
</body>
</html>"""


def _page(error="", status=200):
    return render_template_string(_LOGIN_HTML, error=error), status


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if pin_valid(session.get("pin")):
            return redirect(url_for("stream.index"))
        return _page()

    ip = request.remote_addr or "-"
    fails, blocked_until = _fails.get(ip, (0, 0))
    if time.time() < blocked_until:
        wait = int(blocked_until - time.time()) + 1
        return _page(f"Terlalu banyak percobaan. Coba lagi {wait} detik lagi.", 429)

    pin = (request.form.get("pin") or "").strip()
    if pin_valid(pin):
        _fails.pop(ip, None)
        session.clear()
        session.permanent = True
        session["pin"] = pin
        return redirect(url_for("stream.index"))

    fails += 1
    if fails >= _MAX_FAILS:
        _fails[ip] = (0, time.time() + _BLOCK_SEC)
        return _page("Terlalu banyak percobaan. Tunggu 1 menit.", 429)
    _fails[ip] = (fails, 0)
    return _page("PIN salah.", 401)


@auth_bp.before_app_request
def _gate():
    if request.endpoint in ("auth.login", "static"):
        return
    if pin_valid(session.get("pin")):
        return
    session.clear()
    return redirect(url_for("auth.login"))

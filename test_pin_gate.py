"""Cek PIN gate — jalankan dari folder proyek: python test_pin_gate.py"""
import time
from datetime import timedelta

from flask import Blueprint, Flask

from config import PIN_VALID_HOURS, pin_at, pin_valid
from routes.auth import auth_bp

# PIN = dd + HH + MM
assert pin_at(time.mktime((2026, 10, 7, 14, 35, 0, 0, 0, -1))) == "071435"
assert pin_at(time.mktime((2026,  1, 9,  3,  4, 0, 0, 0, -1))) == "090304"

now = time.mktime((2026, 10, 7, 20, 0, 0, 0, 0, -1))
assert pin_valid("072000", now)            # PIN saat ini
assert pin_valid("071435", now)            # 5j25m lalu, masih dalam 6 jam
assert pin_valid("071400", now)            # tepat 6 jam lalu (inklusif)
assert not pin_valid("071359", now)        # 6j1m lalu
assert not pin_valid("071435", now + 3600)
assert not pin_valid("", now) and not pin_valid(None, now)
assert not pin_valid("abc123", now)

app = Flask(__name__)
app.secret_key = "test"
app.permanent_session_lifetime = timedelta(hours=PIN_VALID_HOURS)
app.register_blueprint(auth_bp)
stub = Blueprint("stream", __name__)
stub.add_url_rule("/", "index", lambda: "OK")
stub.add_url_rule("/status", "status", lambda: "status")
app.register_blueprint(stub)

pin = pin_at()
c = app.test_client()
assert c.get("/").status_code == 302                       # belum login -> /login
html = c.get("/login").get_data(as_text=True)
assert c.get("/login").status_code == 200
assert 'placeholder="XXXXXX"' in html                # placeholder X
assert "length===6" in html and "form.submit()" in html    # auto-submit 6 digit
assert '<button type="submit">Masuk</button>' in html      # tombol tetap ada (fallback)
assert c.post("/login", data={"pin": "999999"}).status_code == 401
assert c.get("/").status_code == 302                       # salah -> tetap terkunci
assert c.post("/login", data={"pin": pin}).status_code == 302
assert c.get("/").get_data(as_text=True) == "OK"           # benar -> terbuka

c2 = app.test_client()
c2.set_cookie("session", "garbage")
assert c2.get("/").status_code == 302

c3 = app.test_client()                                     # brute force -> diblokir
codes = [c3.post("/login", data={"pin": "000000"}).status_code for _ in range(8)]
assert codes[-1] == 429, codes
assert c3.post("/login", data={"pin": pin}).status_code == 429

print("OK — PIN gate lulus. PIN sekarang:", pin)

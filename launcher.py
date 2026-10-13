import os
import sys
import threading
import multiprocessing
import time
import socket
import ssl
import http.server
from urllib.request import urlopen
import pystray
from PIL import Image, ImageDraw
import uvicorn
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from datetime import datetime, timedelta, timezone
import subprocess

# 1. SETUP THU MUC
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    DATA_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = BASE_DIR

# THU MUC GHI FILE (cho log va cert, tranh loi Permission trong Program Files)
USER_DATA_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'STTWordH2M')
try:
    os.makedirs(USER_DATA_DIR, exist_ok=True)
except Exception:
    pass

# NGĂN CRASH KHI CHAY NGAM (CONSOLE=FALSE) VA GHI LOG LOI
log_path = os.path.join(USER_DATA_DIR, 'stt_error.log')
if sys.stdout is None or sys.stderr is None:
    try:
        sys.stdout = sys.stderr = open(log_path, 'a', encoding='utf-8')
    except Exception:
        pass

# 2. TU TAO SSL CERT
def generate_self_signed_cert(cert_path, key_path):
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return
    print("Tạo self-signed SSL cert...")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"STTWord Localhost"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.now(timezone.utc)
    ).not_valid_after(
        datetime.now(timezone.utc) + timedelta(days=3650)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
        critical=False
    ).sign(key, hashes.SHA256())

    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

# 3. HTTP SERVER (PORT 3009)
class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()
        
def start_https_server():
    cert_path = os.path.join(USER_DATA_DIR, "localhost.crt")
    key_path = os.path.join(USER_DATA_DIR, "localhost.key")
    
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        generate_self_signed_cert(cert_path, key_path)
        try:
            print("Đăng ký cert vao Windows Trusted Root...")
            subprocess.run(['certutil', '-user', '-addstore', 'Root', cert_path], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            pass
            
    os.chdir(BASE_DIR)
    httpd = http.server.HTTPServer(('localhost', 3009), CORSRequestHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    httpd.serve_forever()

# 4. STT SERVER (PORT 8009) - CHAY BANG MULTIPROCESSING DE CHONG FORK BOMB
def run_uvicorn():
    sys.path.insert(0, os.path.join(BASE_DIR, "SpeechFunc"))
    from server_stt import app as stt_app, init_engine
    init_engine()
    uvicorn.run(stt_app, host="0.0.0.0", port=8009, log_level="error")

# 5. TRAY ICON
def create_image():
    icon_path = os.path.join(BASE_DIR, 'app_icon.ico')
    if os.path.exists(icon_path):
        try:
            return Image.open(icon_path)
        except Exception:
            pass
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), color=(30, 30, 30))
    dc = ImageDraw.Draw(image)
    dc.ellipse((10, 10, 54, 54), fill=(0, 128, 255))
    return image

# Bien global luu process
stt_process = None

def on_quit(icon, item):
    if stt_process:
        stt_process.terminate()
    icon.stop()
    os._exit(0)

def main():
    global stt_process
    threading.Thread(target=start_https_server, daemon=True).start()
    
    # Khoi dong STT bang Process rieng, cach ly hoan toan khoi Main
    stt_process = multiprocessing.Process(target=run_uvicorn, daemon=True)
    stt_process.start()
    
    # Lay ten thu muc CAI DAT (DATA_DIR thay vi thu muc tmp BASE_DIR)
    share_name = os.path.basename(DATA_DIR)
    dynamic_share_path = rf"\\localhost\{share_name}"

    def copy_catalog_path(icon, item):
        subprocess.run("clip", text=True, input=dynamic_share_path, shell=True)
        try:
            icon.notify(f"Đã copy: {dynamic_share_path}", "STTWordH2M")
        except:
            pass

    icon = pystray.Icon("STTWordH2M", create_image(), "STTWordH2M Add-in", menu=pystray.Menu(
        pystray.MenuItem("Đang chạy (Port 3009 & 8009)", lambda: None, enabled=False),
        pystray.MenuItem(f"📋 Copy Catalog URL: {dynamic_share_path}", copy_catalog_path),
        pystray.MenuItem("Thoát", on_quit)
    ))
    icon.run()

if __name__ == "__main__":
    # LENH NAY CUC KY QUAN TRONG DE NGĂN PYINSTALLER BAT APP VO HAN LAN
    multiprocessing.freeze_support()
    main()

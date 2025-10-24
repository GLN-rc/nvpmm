# send_email.py (robust HTML reader + Gmail SMTP)
import os, sys, smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SENDER = os.environ.get("EMAIL_FROM")          # Gmail address used to create the App Password
RECIPS = [e.strip() for e in os.environ.get("EMAIL_TO","").split(",") if e.strip()]
APP_PW = os.environ.get("EMAIL_PASSWORD")      # 16-char Gmail App Password

if not (SENDER and RECIPS and APP_PW):
    sys.stderr.write("Missing EMAIL_FROM / EMAIL_TO / EMAIL_PASSWORD\n")
    sys.exit(1)

# --- robust read of report.html ---
html_bytes = None
try:
    with open("report.html", "rb") as f:
        html_bytes = f.read()
except FileNotFoundError:
    sys.stderr.write("report.html not found\n")
    sys.exit(1)

def decode_html(b: bytes) -> str:
    # Try common encodings safely
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    # Last resort: replace bad bytes
    return b.decode("utf-8", errors="replace")

html = decode_html(html_bytes)

# --- build message ---
msg = MIMEMultipart("alternative")
msg["From"] = SENDER
msg["To"] = ", ".join(RECIPS)

# Optional: auto-date the subject line (comment out if you prefer static)
try:
    from datetime import date, timedelta
    end = date.today()
    start = end - timedelta(days=6)
    msg["Subject"] = f"ReplicaRivals — Weekly Snapshot ({start:%b %d}–{end:%b %d, %Y})"
except Exception:
    msg["Subject"] = "ReplicaRivals — Weekly Competitive Snapshot"

msg.attach(MIMEText(html, "html", "utf-8"))

# --- send via Gmail SMTP with App Password ---
ctx = ssl.create_default_context()
with smtplib.SMTP("smtp.gmail.com", 587, timeout=60) as server:
    server.ehlo()
    server.starttls(context=ctx)
    server.ehlo()
    server.login(SENDER, APP_PW)
    server.sendmail(SENDER, RECIPS, msg.as_string())

print("✅ Email sent to:", RECIPS)

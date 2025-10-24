import os, sys, smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SENDER = os.environ.get("EMAIL_FROM")          # your Gmail address
RECIPS = [e.strip() for e in os.environ.get("EMAIL_TO","").split(",") if e.strip()]
APP_PW = os.environ.get("EMAIL_PASSWORD")      # 16-char Gmail App Password

if not (SENDER and RECIPS and APP_PW):
    sys.stderr.write("Missing EMAIL_FROM / EMAIL_TO / EMAIL_PASSWORD\n")
    sys.exit(1)

with open("report.html","r",encoding="utf-8") as f:
    html = f.read()

msg = MIMEMultipart("alternative")
msg["Subject"] = "ReplicaRivals — Weekly Competitive Snapshot"
msg["From"] = SENDER
msg["To"] = ", ".join(RECIPS)
msg.attach(MIMEText(html, "html", "utf-8"))

ctx = ssl.create_default_context()
with smtplib.SMTP("smtp.gmail.com", 587, timeout=60) as server:
    server.ehlo(); server.starttls(context=ctx); server.ehlo()
    server.login(SENDER, APP_PW)
    server.sendmail(SENDER, RECIPS, msg.as_string())

print("✅ Email sent to:", RECIPS)

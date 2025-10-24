
# filename: weekly_snapshot.py

import openai
import smtplib
from email.mime.text import MIMEText
import os

# Environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Define the snapshot prompt
prompt = """
Please generate this week's competitive snapshot in HTML format.

Company: Replica
Competitors: Menlo Security, Cyberinc, Cloudflare Browser Isolation, Authentic8 (Silo), Kasm Technologies, Fortanix, NetAbstraction
Regions: North America, EU
Focus Areas: Partnerships, Product Releases, Hiring, M&A, Posted Marketing Content
Audience: Executive team, Sales, Product, Marketing

Use the following HTML structure:
- TL;DR summary
- Table with key events (date, company, event summary with link, tag)
- Role-based takeaways (Marketing, Sales, Product, ELT)
"""

# Call OpenAI with HTML format request
response = openai.ChatCompletion.create(
    model="gpt-5",
    messages=[
        {"role": "system", "content": "You are ReplicaRivals, a competitive intelligence agent. Respond in clean HTML email format only."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.3,
    max_tokens=1800
)

html_content = response['choices'][0]['message']['content']

# Create HTML email
msg = MIMEText(html_content, "html")
msg["Subject"] = "ReplicaRivals – Weekly Competitive Snapshot"
msg["From"] = EMAIL_FROM
msg["To"] = EMAIL_TO

# Send via Gmail SMTP
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(EMAIL_FROM, EMAIL_PASSWORD)
    server.send_message(msg)

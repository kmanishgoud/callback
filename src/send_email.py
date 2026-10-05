"""
Send the report through Gmail, with the charts embedded in the email.

Credentials come from the .env file in the project root (never from the code).
"""
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

import config

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465     # SSL


def load_settings() -> dict:
    """Read email settings from .env and fail with a clear message if any are missing."""
    load_dotenv(config.ROOT / ".env")
    settings = {
        "sender": os.getenv("GMAIL_ADDRESS"),
        "password": os.getenv("GMAIL_APP_PASSWORD"),
        "recipient": os.getenv("REPORT_TO"),
    }
    missing = [k for k, v in settings.items() if not v]
    if missing:
        raise RuntimeError(f"Missing email settings in .env: {missing}. See .env.example.")
    return settings


def build_message(subject: str, html: str, text: str, chart_paths: dict[str, Path],
                  sender: str, recipient: str) -> EmailMessage:
    """An email with a plain-text fallback, an HTML version, and the charts embedded inline."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    msg.set_content(text)                       # shown by email apps that can't display HTML
    msg.add_alternative(html, subtype="html")

    # Attach each chart to the HTML part; the template refers to them as cid:funnel, cid:trend, ...
    html_part = msg.get_payload()[1]
    for name, path in chart_paths.items():
        html_part.add_related(path.read_bytes(), maintype="image", subtype="png", cid=f"<{name}>")
    return msg


def send_message(msg: EmailMessage, settings: dict) -> None:
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(settings["sender"], settings["password"])
        server.send_message(msg)
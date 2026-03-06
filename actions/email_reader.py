"""
Email reader for Sam via IMAP (Gmail / Outlook).

Setup required in config/api_keys.json:
    "email_address": "you@gmail.com",
    "email_password": "your-app-password",
    "imap_server": "imap.gmail.com"        (optional, defaults to Gmail)

For Gmail: enable 2FA and create an App Password.
For Outlook: use imap-mail.outlook.com and your regular password.
"""

import imaplib
import email
import email.header
import json
import os
from pathlib import Path
from log.logger import get_logger

logger = get_logger("EMAIL")

DEFAULT_IMAP = "imap.gmail.com"


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "api_keys.json"
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _decode_header(raw) -> str:
    parts = email.header.decode_header(raw or "")
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)


def get_unread_emails(max_count: int = 5) -> list[dict]:
    """
    Connect to IMAP and return up to max_count unread emails.
    Each item: {from, subject, preview}
    """
    cfg = _load_config()
    address = cfg.get("email_address") or os.getenv("EMAIL_ADDRESS")
    password = cfg.get("email_password") or os.getenv("EMAIL_PASSWORD")
    server = cfg.get("imap_server", DEFAULT_IMAP)

    if not address or not password:
        return [{"error": "Email credentials not configured. Add email_address and email_password to config/api_keys.json."}]

    try:
        mail = imaplib.IMAP4_SSL(server)
        mail.login(address, password)
        mail.select("inbox")

        _, uids = mail.search(None, "UNSEEN")
        uid_list = uids[0].split()
        recent = uid_list[-max_count:]

        results = []
        for uid in reversed(recent):
            _, data = mail.fetch(uid, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            subject = _decode_header(msg.get("Subject", "(no subject)"))
            sender = _decode_header(msg.get("From", "Unknown"))

            # Extract plain-text preview
            preview = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        preview = part.get_payload(decode=True).decode(errors="replace")[:200]
                        break
            else:
                preview = msg.get_payload(decode=True).decode(errors="replace")[:200]

            results.append({"from": sender, "subject": subject, "preview": preview.strip()})

        mail.logout()
        return results

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP error: {e}")
        return [{"error": f"IMAP login failed: {e}"}]
    except Exception as e:
        logger.error(f"Email read failed: {e}")
        return [{"error": str(e)}]

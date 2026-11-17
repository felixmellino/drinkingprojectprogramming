"""Send recovery codes through a configured SMTP server using TLS."""

import os
import smtplib
import ssl
from email.message import EmailMessage


class MailUnavailable(RuntimeError):
    pass


def mail_settings() -> dict:
    import streamlit as st

    settings = {}
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"):
        try:
            value = st.secrets.get(key)
        except Exception:
            value = None
        settings[key] = value or os.environ.get(key)
    if not all(settings.values()):
        raise MailUnavailable("Password recovery is unavailable. Contact the app administrator.")
    try:
        settings["SMTP_PORT"] = int(settings["SMTP_PORT"])
    except ValueError as exc:
        raise MailUnavailable("Password recovery is unavailable. Contact the app administrator.") from exc
    return settings


def send_reset_code(email: str, code: str, settings: dict) -> None:
    message = EmailMessage()
    message["Subject"] = "Reset your WeGoPub password"
    message["From"] = settings["SMTP_FROM"]
    message["To"] = email
    message.set_content(
        "Paste this code into Forgot password in WeGoPub:\n\n"
        f"{code}\n\nThis code expires in 15 minutes and can be used once.\n"
        "If you did not request this, you can ignore this email."
    )
    try:
        if settings["SMTP_PORT"] == 465:
            with smtplib.SMTP_SSL(settings["SMTP_HOST"], 465, timeout=10, context=ssl.create_default_context()) as server:
                server.login(settings["SMTP_USER"], settings["SMTP_PASSWORD"])
                server.send_message(message)
        else:
            with smtplib.SMTP(settings["SMTP_HOST"], settings["SMTP_PORT"], timeout=10) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(settings["SMTP_USER"], settings["SMTP_PASSWORD"])
                server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise MailUnavailable("Password recovery is unavailable. Contact the app administrator.") from exc

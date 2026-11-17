import smtplib
from unittest.mock import patch

import pytest

from data.mail import MailUnavailable, send_reset_code


SETTINGS = {
    "SMTP_HOST": "smtp.example.com", "SMTP_PORT": 465,
    "SMTP_USER": "user", "SMTP_PASSWORD": "secret", "SMTP_FROM": "noreply@example.com",
}


@pytest.mark.parametrize("port,transport", [(465, "SMTP_SSL"), (587, "SMTP")])
def test_reset_email_is_sent_over_tls(port, transport):
    with patch(f"data.mail.smtplib.{transport}") as connection:
        send_reset_code("mia@example.com", "one-time-code", {**SETTINGS, "SMTP_PORT": port})
        server = connection.return_value.__enter__.return_value
        if port == 587:
            server.starttls.assert_called_once()
        server.login.assert_called_once_with("user", "secret")
        message = server.send_message.call_args.args[0]
        assert message["To"] == "mia@example.com"
        assert "one-time-code" in message.get_content()
        assert "15 minutes" in message.get_content()


def test_mail_failure_does_not_expose_smtp_credentials():
    with patch("data.mail.smtplib.SMTP_SSL", side_effect=smtplib.SMTPAuthenticationError(535, b"secret")):
        with pytest.raises(MailUnavailable) as failure:
            send_reset_code("mia@example.com", "code", SETTINGS)
        assert "secret" not in str(failure.value)

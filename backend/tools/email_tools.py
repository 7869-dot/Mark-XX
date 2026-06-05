import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import SMTP_HOST, SMTP_PORT, EMAIL_ADDRESS, EMAIL_APP_PASSWORD


def send_email(to: str, subject: str, body: str) -> str:
    """Send an email via SMTP (Gmail by default).
    Swap EMAIL_ADDRESS / EMAIL_APP_PASSWORD for Resend/SendGrid by replacing
    this function — the caller interface stays the same.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to, msg.as_string())

    return f"Email successfully sent to {to}."

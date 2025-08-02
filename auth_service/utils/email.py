import smtplib
import ssl
from email.mime.text import MIMEText
from config import settings

def send_otp_email(to_email: str, otp: str):
    msg = MIMEText(f"Your verification code is: {otp}\n\nValid for 5 minutes.")
    msg["Subject"] = "Your Verification Code"
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to_email

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(settings.SMTP_USER, settings.SMTP_PASS)
        server.send_message(msg)

def send_password_reset_email(to_email: str, reset_link: str):
    body = f"""
    You requested a password reset. Click the link below to continue:
    {reset_link}
    
    This link expires in 15 minutes. If you didn't request this, please ignore this email.
    """
    msg = MIMEText(body.strip())
    msg["Subject"] = "Password Reset Instructions"
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to_email

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(settings.SMTP_USER, settings.SMTP_PASS)
        server.send_message(msg)
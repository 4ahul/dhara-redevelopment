import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER)
FROM_NAME = os.environ.get("FROM_NAME", "Dhara RAG")


def send_email(
    to_email: str, subject: str, html_content: str, text_content: Optional[str] = None
) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.info(f"[EMAIL] Mock send to {to_email}: {subject}")
        logger.info(f"[EMAIL] Content preview: {text_content or html_content[:200]}...")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"] = to_email

        text_part = MIMEText(text_content or html_content, "plain")
        html_part = MIMEText(html_content, "html")

        msg.attach(text_part)
        msg.attach(html_part)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, [to_email], msg.as_string())

        logger.info(f"[EMAIL] Sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"[EMAIL] Failed to send to {to_email}: {e}", exc_info=True)
        return False


def send_verification_email(to_email: str, verification_link: str) -> bool:
    subject = "Verify your Dhara RAG account"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #2563eb; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
            .button {{ display: inline-block; background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Dhara RAG</h1>
            </div>
            <div class="content">
                <h2>Verify Your Email Address</h2>
                <p>Thank you for signing up for Dhara RAG. Please click the button below to verify your email address:</p>
                <p style="text-align: center;">
                    <a href="{verification_link}" class="button">Verify Email</a>
                </p>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #6b7280; font-size: 14px;">{verification_link}</p>
                <p>This link will expire in 24 hours.</p>
                <p>If you didn't create an account with Dhara RAG, please ignore this email.</p>
            </div>
            <div class="footer">
                <p>Dhara RAG - PMC Regulatory Intelligence</p>
            </div>
        </div>
    </body>
    </html>
    """
    text_content = f"""
    Verify your Dhara RAG account
    
    Thank you for signing up for Dhara RAG. Please click the link below to verify your email address:
    
    {verification_link}
    
    This link will expire in 24 hours.
    
    If you didn't create an account with Dhara RAG, please ignore this email.
    """
    return send_email(to_email, subject, html_content, text_content)


def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    subject = "Reset your Dhara RAG password"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #dc2626; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
            .button {{ display: inline-block; background: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Dhara RAG</h1>
            </div>
            <div class="content">
                <h2>Reset Your Password</h2>
                <p>We received a request to reset your password. Click the button below to create a new password:</p>
                <p style="text-align: center;">
                    <a href="{reset_link}" class="button">Reset Password</a>
                </p>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #6b7280; font-size: 14px;">{reset_link}</p>
                <p>This link will expire in 1 hour.</p>
                <p>If you didn't request a password reset, please ignore this email and your password will remain unchanged.</p>
            </div>
            <div class="footer">
                <p>Dhara RAG - PMC Regulatory Intelligence</p>
            </div>
        </div>
    </body>
    </html>
    """
    text_content = f"""
    Reset your Dhara RAG password
    
    We received a request to reset your password. Click the link below to create a new password:
    
    {reset_link}
    
    This link will expire in 1 hour.
    
    If you didn't request a password reset, please ignore this email.
    """
    return send_email(to_email, subject, html_content, text_content)


def send_welcome_email(to_email: str, full_name: str) -> bool:
    subject = "Welcome to Dhara RAG"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #2563eb; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
            .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Dhara RAG</h1>
            </div>
            <div class="content">
                <h2>Welcome, {full_name}!</h2>
                <p>Your Dhara RAG account has been successfully verified. You can now start using our PMC Regulatory Intelligence platform.</p>
                <p>With Dhara RAG, you can:</p>
                <ul>
                    <li>Query DCPR 2034 regulations using AI-powered semantic search</li>
                    <li>Analyze property feasibility for redevelopment projects</li>
                    <li>Generate compliance reports</li>
                    <li>Track workflow progress</li>
                </ul>
                <p>Get started by asking your first regulatory question!</p>
            </div>
            <div class="footer">
                <p>Dhara RAG - PMC Regulatory Intelligence</p>
            </div>
        </div>
    </body>
    </html>
    """
    text_content = f"""
    Welcome, {full_name}!
    
    Your Dhara RAG account has been successfully verified. You can now start using our PMC Regulatory Intelligence platform.
    
    With Dhara RAG, you can:
    - Query DCPR 2034 regulations using AI-powered semantic search
    - Analyze property feasibility for redevelopment projects
    - Generate compliance reports
    - Track workflow progress
    
    Get started by asking your first regulatory question!
    """
    return send_email(to_email, subject, html_content, text_content)

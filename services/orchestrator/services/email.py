"""
Dhara AI — Email Service
Async SMTP email sending with Jinja2 HTML templates.
"""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from jinja2 import BaseLoader, Environment

from ..core.config import settings

logger = logging.getLogger(__name__)

# ─── Templates ───────────────────────────────────────────────────────────────

TEMPLATES = {
    "team_invite": """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body{font-family:'Segoe UI',Arial,sans-serif;background:#f4f7fa;margin:0;padding:0}
.c{max-width:600px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)}
.h{background:linear-gradient(135deg,#1a237e,#283593);padding:32px;text-align:center}
.h h1{color:#fff;margin:0;font-size:24px} .b{padding:32px} .b p{color:#37474f;line-height:1.7;font-size:15px}
.cta{display:inline-block;background:#1a237e;color:#fff !important;padding:14px 36px;border-radius:8px;text-decoration:none;font-weight:600;margin:20px 0}
.f{background:#f4f7fa;padding:20px;text-align:center;color:#90a4ae;font-size:12px}
</style></head><body><div class="c">
<div class="h"><h1>Dhara AI — Team Invitation</h1></div>
<div class="b"><p>Hello {{ name or 'there' }},</p>
<p><strong>{{ inviter_name }}</strong> invited you to join as <strong>{{ role }}</strong>.</p>
<p style="text-align:center"><a href="{{ invite_url }}" class="cta">Accept Invitation</a></p></div>
<div class="f">© {{ year }} Dhara AI. All rights reserved.</div></div></body></html>""",
    "get_started_confirmation": """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body{font-family:'Segoe UI',Arial,sans-serif;background:#f4f7fa;margin:0;padding:0}
.c{max-width:600px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)}
.h{background:linear-gradient(135deg,#1a237e,#283593);padding:32px;text-align:center}
.h h1{color:#fff;margin:0;font-size:24px} .b{padding:32px} .b p{color:#37474f;line-height:1.7;font-size:15px}
.f{background:#f4f7fa;padding:20px;text-align:center;color:#90a4ae;font-size:12px}
</style></head><body><div class="c">
<div class="h"><h1>Welcome to Dhara AI</h1></div>
<div class="b"><p>Hello {{ name }},</p><p>Thank you for your interest! Reference: <strong>{{ reference_id }}</strong></p>
{% if society_name %}<p>Society: {{ society_name }}</p>{% endif %}
<p>We'll get back to you within 24 hours.</p></div>
<div class="f">© {{ year }} Dhara AI. All rights reserved.</div></div></body></html>""",
    "contact_confirmation": """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body{font-family:'Segoe UI',Arial,sans-serif;background:#f4f7fa;margin:0;padding:0}
.c{max-width:600px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)}
.h{background:linear-gradient(135deg,#1a237e,#283593);padding:32px;text-align:center}
.h h1{color:#fff;margin:0;font-size:24px} .b{padding:32px} .b p{color:#37474f;line-height:1.7;font-size:15px}
.f{background:#f4f7fa;padding:20px;text-align:center;color:#90a4ae;font-size:12px}
</style></head><body><div class="c">
<div class="h"><h1>Message Received</h1></div>
<div class="b"><p>Hello {{ name }},</p><p>Reference: <strong>{{ reference_id }}</strong></p>
<p>We'll respond within 1-2 business days.</p></div>
<div class="f">© {{ year }} Dhara AI. All rights reserved.</div></div></body></html>""",
    "admin_new_enquiry": """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body{font-family:'Segoe UI',Arial,sans-serif;background:#f4f7fa;margin:0;padding:0}
.c{max-width:600px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)}
.h{background:linear-gradient(135deg,#c62828,#d32f2f);padding:32px;text-align:center}
.h h1{color:#fff;margin:0;font-size:24px} .b{padding:32px} .b p{color:#37474f;line-height:1.7;font-size:15px}
.d{background:#f4f7fa;padding:16px;border-radius:8px;margin:12px 0}
.f{background:#f4f7fa;padding:20px;text-align:center;color:#90a4ae;font-size:12px}
</style></head><body><div class="c">
<div class="h"><h1>New {{ source }}</h1></div>
<div class="b"><div class="d"><p><strong>From:</strong> {{ name }} ({{ email }})</p>
{% if phone %}<p><strong>Phone:</strong> {{ phone }}</p>{% endif %}</div>
<p><strong>Message:</strong> {{ message }}</p><p>Ref: {{ reference_id }}</p></div>
<div class="f">Dhara AI Admin</div></div></body></html>""",
}

_jinja = Environment(loader=BaseLoader())


# ─── Core ────────────────────────────────────────────────────────────────────


async def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
) -> bool:
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        logger.warning("SMTP not configured — skipping email to %s", to_email)
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=False,
            start_tls=settings.SMTP_USE_TLS,
        )
        logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        return False


def _render(template_name: str, **ctx) -> str:
    from datetime import datetime

    ctx.setdefault("year", datetime.utcnow().year)
    return _jinja.from_string(TEMPLATES[template_name]).render(**ctx)


# ─── Helpers ─────────────────────────────────────────────────────────────────


async def send_team_invite(
    to_email: str, inviter_name: str, role: str, invite_url: str, name: str | None = None
) -> bool:
    html = _render(
        "team_invite", name=name, inviter_name=inviter_name, role=role, invite_url=invite_url
    )
    return await send_email(to_email, f"{inviter_name} invited you to Dhara AI", html)


async def send_get_started_confirmation(
    to_email: str, name: str, reference_id: str, society_name: str | None = None
) -> bool:
    html = _render(
        "get_started_confirmation", name=name, reference_id=reference_id, society_name=society_name
    )
    return await send_email(to_email, "Welcome to Dhara AI", html)


async def send_contact_confirmation(
    to_email: str, name: str, reference_id: str, subject: str | None = None
) -> bool:
    html = _render("contact_confirmation", name=name, reference_id=reference_id, subject=subject)
    return await send_email(to_email, "Dhara AI — Message Received", html)


async def send_admin_notification(
    name: str,
    email: str,
    message: str,
    reference_id: str,
    source: str = "Enquiry",
    phone: str | None = None,
    subject: str | None = None,
    society_name: str | None = None,
) -> bool:
    html = _render(
        "admin_new_enquiry",
        name=name,
        email=email,
        phone=phone,
        subject=subject,
        message=message,
        reference_id=reference_id,
        source=source,
        society_name=society_name,
    )
    return await send_email(settings.SMTP_FROM_EMAIL, f"New {source}: {name}", html)

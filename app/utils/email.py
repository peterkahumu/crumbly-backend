"""SMTP Email delivery service for Crumbly.

Handles password reset and super admin invitation emails via standard SMTP.
When SMTP is not configured (e.g. in development/tests), logs the action
and generated link to console without raising an exception.
"""

import asyncio
from email.message import EmailMessage
from email.utils import formataddr
import logging
import smtplib

from app.config import get_settings

logger = logging.getLogger(__name__)


def _send_smtp_sync(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str | None = None,
) -> bool:
    settings = get_settings()

    if not settings.smtp_host:
        logger.info(
            f"[EMAIL DEV SIMULATION] To: {to_email} | Subject: {subject}\n"
            f"Content Preview:\n{text_content or html_content}"
        )
        return True

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        sender_email = settings.smtp_from_email or settings.smtp_user or "no-reply@crumbly.co.ke"
        msg["From"] = formataddr((settings.smtp_from_name, sender_email))
        msg["To"] = to_email

        plain = text_content or "Please open this email in an HTML-compatible client to view its contents."
        msg.set_content(plain)
        msg.add_alternative(html_content, subtype="html")

        if settings.smtp_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                if settings.smtp_user and settings.smtp_password:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                if settings.smtp_tls:
                    server.starttls()
                if settings.smtp_user and settings.smtp_password:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

        logger.info(f"Successfully sent email to {to_email} via SMTP ({settings.smtp_host})")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email} via SMTP: {e}", exc_info=True)
        return False


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str | None = None,
) -> bool:
    """Send an email asynchronously in a worker thread."""
    return await asyncio.to_thread(
        _send_smtp_sync,
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )


async def send_password_reset_email(
    to_email: str,
    reset_url: str,
    recipient_name: str | None = None,
) -> bool:
    """Send a self-service password reset email."""
    name = recipient_name or "there"
    subject = "Reset your Crumbly password"

    text_content = f"""Hello {name},

We received a request to reset the password for your Crumbly account ({to_email}).

To set a new password, open this link in your browser:
{reset_url}

This link is valid for 1 hour. If you didn't request a password reset, you can safely ignore this email.

— The Crumbly Team
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #FAF8F5; margin: 0; padding: 40px 20px; color: #2B1E16;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #EAE4DA; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
    <tr>
      <td style="padding: 32px 32px 24px; text-align: center; background: #FFFBF7; border-bottom: 1px solid #F2ECE1;">
        <h1 style="margin: 0; color: #E07A5F; font-size: 26px; font-weight: 700; letter-spacing: -0.5px;">Crumbly</h1>
        <p style="margin: 4px 0 0; color: #7A685D; font-size: 13px;">Artisan Bakeries Marketplace</p>
      </td>
    </tr>
    <tr>
      <td style="padding: 32px;">
        <h2 style="margin: 0 0 16px; font-size: 20px; color: #2B1E16; font-weight: 600;">Reset your password</h2>
        <p style="margin: 0 0 20px; font-size: 15px; line-height: 1.6; color: #53453D;">
          Hello <strong>{name}</strong>, we received a request to reset the password for your Crumbly account (<strong>{to_email}</strong>).
        </p>
        <p style="margin: 0 0 28px; font-size: 15px; line-height: 1.6; color: #53453D;">
          Click the button below to choose a new password:
        </p>
        <div style="text-align: center; margin: 30px 0;">
          <a href="{reset_url}" target="_blank" style="background-color: #E07A5F; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 15px; display: inline-block; box-shadow: 0 2px 6px rgba(224,122,95,0.3);">Reset Password</a>
        </div>
        <p style="margin: 28px 0 12px; font-size: 13px; color: #8F7D73; line-height: 1.5;">
          This link will expire in <strong>1 hour</strong>. If the button above does not work, copy and paste this link into your browser:
        </p>
        <p style="margin: 0 0 24px; font-size: 12px; word-break: break-all; color: #E07A5F;">
          <a href="{reset_url}" style="color: #E07A5F; text-decoration: underline;">{reset_url}</a>
        </p>
        <hr style="border: none; border-top: 1px solid #F0EAE1; margin: 24px 0;" />
        <p style="margin: 0; font-size: 12px; color: #A89B92; line-height: 1.5;">
          If you did not request this password reset, no action is needed. Your account remains safe and unchanged.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return await send_email(to_email, subject, html_content, text_content)


async def send_admin_invitation_email(
    to_email: str,
    setup_url: str,
    recipient_name: str | None = None,
) -> bool:
    """Send an invitation email to a newly provisioned Super Admin to set their password."""
    name = recipient_name or "Administrator"
    subject = "You've been invited as a Crumbly Platform Administrator"

    text_content = f"""Hello {name},

You have been granted Super Administrator access to the Crumbly Marketplace platform.

To set up your account and create your password, open the link below:
{setup_url}

This invitation link is valid for 48 hours. Once configured, you can log in to the Crumbly Admin Dashboard.

If you were not expecting this invitation, please contact your team administrator.

— The Crumbly Team
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #FAF8F5; margin: 0; padding: 40px 20px; color: #2B1E16;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #EAE4DA; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
    <tr>
      <td style="padding: 32px 32px 24px; text-align: center; background: #FFFBF7; border-bottom: 1px solid #F2ECE1;">
        <h1 style="margin: 0; color: #E07A5F; font-size: 26px; font-weight: 700; letter-spacing: -0.5px;">Crumbly</h1>
        <p style="margin: 4px 0 0; color: #7A685D; font-size: 13px;">Platform Administration</p>
      </td>
    </tr>
    <tr>
      <td style="padding: 32px;">
        <h2 style="margin: 0 0 16px; font-size: 20px; color: #2B1E16; font-weight: 600;">Welcome to the Crumbly Team</h2>
        <p style="margin: 0 0 20px; font-size: 15px; line-height: 1.6; color: #53453D;">
          Hello <strong>{name}</strong>, you have been invited to join Crumbly as a <strong>Platform Administrator</strong> (<strong>{to_email}</strong>).
        </p>
        <p style="margin: 0 0 28px; font-size: 15px; line-height: 1.6; color: #53453D;">
          For security, your password is not pre-set. Click the button below to choose your private password and activate your administrator account:
        </p>
        <div style="text-align: center; margin: 30px 0;">
          <a href="{setup_url}" target="_blank" style="background-color: #E07A5F; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 15px; display: inline-block; box-shadow: 0 2px 6px rgba(224,122,95,0.3);">Set Your Admin Password</a>
        </div>
        <p style="margin: 28px 0 12px; font-size: 13px; color: #8F7D73; line-height: 1.5;">
          This link will expire in <strong>48 hours</strong>. If the button above does not work, copy and paste this link into your browser:
        </p>
        <p style="margin: 0 0 24px; font-size: 12px; word-break: break-all; color: #E07A5F;">
          <a href="{setup_url}" style="color: #E07A5F; text-decoration: underline;">{setup_url}</a>
        </p>
        <hr style="border: none; border-top: 1px solid #F0EAE1; margin: 24px 0;" />
        <p style="margin: 0; font-size: 12px; color: #A89B92; line-height: 1.5;">
          Once set, you will be able to access the admin dashboard to manage bakeries, platform analytics, orders, and customer inquiries.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return await send_email(to_email, subject, html_content, text_content)

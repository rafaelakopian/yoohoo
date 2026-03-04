"""Security email templates and device fingerprinting.

Provides:
- Device fingerprinting (UA normalization + SHA256)
- New device login alert (check + email)
- 2FA lifecycle emails (enabled, disabled, backup code used, admin reset)

All templates return tuple[str, str] (subject, html_body) and use the shared
_base_template for consistent branding.
"""

import hashlib
import re
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.email import EmailSender, escape, send_email_safe

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# UA Normalization + Fingerprint
# ---------------------------------------------------------------------------

_BROWSER_RE = re.compile(
    r"(chrome|firefox|safari|edge|opera|brave|vivaldi|samsung)"
    r"[/ ]+(\d+)",
    re.IGNORECASE,
)
_OS_PATTERNS: list[tuple[str, str]] = [
    (r"android", "android"),
    (r"iphone|ipad|ipod", "ios"),
    (r"windows", "windows"),
    (r"mac os|macintosh", "macos"),
    (r"cros", "chromeos"),
    (r"linux", "linux"),
]


def _normalize_ua(user_agent: str | None) -> str:
    """Extract browser family + major version + OS from User-Agent.

    Produces a stable string that doesn't change on minor browser updates,
    e.g. "chrome/120 windows" or "safari/17 macos".
    """
    if not user_agent:
        return "unknown"
    ua = user_agent.strip().lower()

    # Browser family + major version
    m = _BROWSER_RE.search(ua)
    browser = f"{m.group(1)}/{m.group(2)}" if m else "other"

    # OS detection
    os_name = "other"
    for pattern, name in _OS_PATTERNS:
        if re.search(pattern, ua):
            os_name = name
            break

    return f"{browser} {os_name}"


def compute_device_fingerprint(user_agent: str | None) -> str:
    """Compute a SHA256 fingerprint from the normalized User-Agent.

    Returns a 64-char hex string suitable for database storage and comparison.
    """
    normalized = _normalize_ua(user_agent)
    return hashlib.sha256(normalized.encode()).hexdigest()


# ---------------------------------------------------------------------------
# New Device Detection
# ---------------------------------------------------------------------------

async def check_and_alert_new_device(
    db: AsyncSession,
    user_id: str,
    email: str,
    full_name: str,
    user_agent: str | None,
    ip_address: str | None,
) -> None:
    """Check if this is a new device for the user and send an alert email.

    Must be called BEFORE inserting the new RefreshToken to avoid counting it.

    Logic:
    1. Count existing tokens → 0 means first login, skip alert
    2. Check if fingerprint is already known (including revoked tokens)
    3. If unknown → send new device alert email
    """
    from app.modules.platform.auth.models import RefreshToken

    try:
        # 1. Count total tokens for user (any state)
        count_q = select(func.count()).where(RefreshToken.user_id == user_id)
        result = await db.execute(count_q)
        total = result.scalar() or 0

        if total == 0:
            # First ever login — no comparison data, skip alert
            return

        # 2. Compute fingerprint
        fingerprint = compute_device_fingerprint(user_agent)

        # 3. Check if this fingerprint is known (revoked or active)
        known_q = select(func.count()).where(
            RefreshToken.user_id == user_id,
            RefreshToken.device_fingerprint == fingerprint,
        )
        result = await db.execute(known_q)
        known = result.scalar() or 0

        if known > 0:
            return  # Known device

        # 4. New device — send alert
        sessions_url = f"{settings.frontend_url}/auth/account?tab=sessions"
        subject, html = build_new_device_email(
            full_name, ip_address, user_agent, sessions_url
        )
        await send_email_safe(email, subject, html, sender=EmailSender.SECURITY)
        logger.info(
            "security_email.new_device_alert",
            user_id=user_id,
            fingerprint=fingerprint[:12],
        )

    except Exception:
        # Never block login for email failures
        logger.warning(
            "security_email.failed",
            action="new_device_check",
            user_id=user_id,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Shared Context Block
# ---------------------------------------------------------------------------

def _security_context_html(
    ip_address: str | None = None,
    user_agent: str | None = None,
    sessions_url: str | None = None,
) -> str:
    """Build an HTML context block with timestamp, IP, device, and sessions link."""
    now = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M UTC")
    ua_display = (user_agent or "Onbekend")[:100]

    rows = f"""
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <tr>
        <td style="padding:6px 12px;border:1px solid #e5e7eb;color:#202b40;font-weight:bold;font-size:13px;">Tijdstip</td>
        <td style="padding:6px 12px;border:1px solid #e5e7eb;color:#767a81;font-size:13px;">{escape(now)}</td>
      </tr>
      <tr>
        <td style="padding:6px 12px;border:1px solid #e5e7eb;color:#202b40;font-weight:bold;font-size:13px;">IP-adres</td>
        <td style="padding:6px 12px;border:1px solid #e5e7eb;color:#767a81;font-size:13px;">{escape(ip_address or 'Onbekend')}</td>
      </tr>
      <tr>
        <td style="padding:6px 12px;border:1px solid #e5e7eb;color:#202b40;font-weight:bold;font-size:13px;">Apparaat</td>
        <td style="padding:6px 12px;border:1px solid #e5e7eb;color:#767a81;font-size:13px;">{escape(ua_display)}</td>
      </tr>
    </table>"""

    if sessions_url:
        rows += f"""
    <p style="color:#767a81;font-size:13px;margin:0 0 8px;">
      <a href="{sessions_url}" style="color:#066aab;text-decoration:underline;">
        Bekijk je actieve sessies
      </a>
    </p>"""

    return rows


# ---------------------------------------------------------------------------
# Email Builders
# ---------------------------------------------------------------------------

def build_new_device_email(
    full_name: str,
    ip_address: str | None,
    user_agent: str | None,
    sessions_url: str,
) -> tuple[str, str]:
    """New device login alert email."""
    from app.modules.tenant.notification.templates import _base_template

    subject = f"Nieuwe inlog op je account — {settings.platform_name}"
    context = _security_context_html(ip_address, user_agent, sessions_url)
    body = f"""
    <p style="color:#202b40;font-size:16px;margin:0 0 16px;">Hallo {escape(full_name)},</p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 8px;">
      Er is zojuist ingelogd op je {settings.platform_name}-account vanaf een nieuw apparaat.
    </p>
    {context}
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:16px 0 0;">
      Was jij dit niet? Wijzig dan onmiddellijk je wachtwoord en controleer je sessies.
    </p>"""
    return subject, _base_template("Nieuwe inlog gedetecteerd", body)


def build_2fa_enabled_email(
    full_name: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    sessions_url: str | None = None,
) -> tuple[str, str]:
    """2FA has been enabled on the account."""
    from app.modules.tenant.notification.templates import _base_template

    if not sessions_url:
        sessions_url = f"{settings.frontend_url}/auth/account?tab=sessions"
    subject = f"Tweefactorauthenticatie ingeschakeld — {settings.platform_name}"
    context = _security_context_html(ip_address, user_agent, sessions_url)
    body = f"""
    <p style="color:#202b40;font-size:16px;margin:0 0 16px;">Hallo {escape(full_name)},</p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 8px;">
      Tweefactorauthenticatie (2FA) is zojuist ingeschakeld op je {settings.platform_name}-account.
      Voortaan heb je naast je wachtwoord ook een code uit je authenticator-app nodig om in te loggen.
    </p>
    {context}
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:16px 0 0;">
      Heb je dit niet zelf gedaan? Neem dan onmiddellijk contact op met je beheerder.
    </p>"""
    return subject, _base_template("2FA ingeschakeld", body)


def build_2fa_disabled_email(
    full_name: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    sessions_url: str | None = None,
) -> tuple[str, str]:
    """2FA has been disabled on the account."""
    from app.modules.tenant.notification.templates import _base_template

    if not sessions_url:
        sessions_url = f"{settings.frontend_url}/auth/account?tab=sessions"
    subject = f"Tweefactorauthenticatie uitgeschakeld — {settings.platform_name}"
    context = _security_context_html(ip_address, user_agent, sessions_url)
    body = f"""
    <p style="color:#202b40;font-size:16px;margin:0 0 16px;">Hallo {escape(full_name)},</p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 8px;">
      Tweefactorauthenticatie (2FA) is zojuist uitgeschakeld op je {settings.platform_name}-account.
      Je account is nu alleen beveiligd met je wachtwoord.
    </p>
    {context}
    <p style="color:#ef4444;font-size:14px;line-height:1.6;margin:16px 0 0;">
      Was dit niet jouw actie? Wijzig dan onmiddellijk je wachtwoord en schakel 2FA opnieuw in.
    </p>"""
    return subject, _base_template("2FA uitgeschakeld", body)


def build_backup_code_used_email(
    full_name: str,
    remaining_count: int,
    sessions_url: str | None = None,
) -> tuple[str, str]:
    """A backup code was used to log in."""
    from app.modules.tenant.notification.templates import _base_template

    if not sessions_url:
        sessions_url = f"{settings.frontend_url}/auth/account?tab=sessions"
    subject = f"Backup code gebruikt — {settings.platform_name}"

    warning = ""
    if remaining_count <= 2:
        warning = f"""
    <p style="color:#ef4444;font-size:14px;font-weight:bold;line-height:1.6;margin:0 0 8px;">
      Let op: je hebt nog maar {remaining_count} backup code(s) over.
      Genereer nieuwe codes in je accountinstellingen.
    </p>"""

    body = f"""
    <p style="color:#202b40;font-size:16px;margin:0 0 16px;">Hallo {escape(full_name)},</p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 8px;">
      Er is zojuist een backup code gebruikt om in te loggen op je {settings.platform_name}-account.
      Je hebt nog <strong>{remaining_count}</strong> backup code(s) over.
    </p>
    {warning}
    <p style="color:#767a81;font-size:13px;margin:8px 0 0;">
      <a href="{sessions_url}" style="color:#066aab;text-decoration:underline;">
        Bekijk je actieve sessies
      </a>
    </p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:16px 0 0;">
      Was dit niet jouw actie? Wijzig dan onmiddellijk je wachtwoord.
    </p>"""
    return subject, _base_template("Backup code gebruikt", body)


def build_2fa_admin_reset_email(
    full_name: str,
    sessions_url: str | None = None,
) -> tuple[str, str]:
    """2FA was reset by a platform admin."""
    from app.modules.tenant.notification.templates import _base_template

    if not sessions_url:
        sessions_url = f"{settings.frontend_url}/auth/account?tab=sessions"
    subject = f"Tweefactorauthenticatie gereset door beheerder — {settings.platform_name}"
    body = f"""
    <p style="color:#202b40;font-size:16px;margin:0 0 16px;">Hallo {escape(full_name)},</p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 8px;">
      Een beheerder heeft de tweefactorauthenticatie (2FA) op je {settings.platform_name}-account
      gereset. Al je actieve sessies zijn beëindigd.
    </p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 8px;">
      Je kunt nu inloggen met alleen je wachtwoord. We raden aan om 2FA opnieuw in
      te schakelen in je accountinstellingen.
    </p>
    <p style="color:#767a81;font-size:13px;margin:8px 0 0;">
      <a href="{sessions_url}" style="color:#066aab;text-decoration:underline;">
        Ga naar je accountinstellingen
      </a>
    </p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:16px 0 0;">
      Heb je deze reset niet aangevraagd? Neem dan contact op met je beheerder.
    </p>"""
    return subject, _base_template("2FA gereset door beheerder", body)

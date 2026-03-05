"""Dutch HTML email templates for notifications.

All templates use centralized platform branding from settings.
Colors: navy header #202b40, primary button #cd095b.
"""

from app.config import settings
from app.core.email import escape


def _base_template(title: str, body_html: str, header_name: str | None = None) -> str:
    """Base email template. header_name overrides the header (e.g. organization name).
    Footer always shows 'Powered by {platform_name}'."""
    header = header_name or settings.platform_name
    platform = settings.platform_name
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background-color:#f6f7fa;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f6f7fa;padding:40px 0;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <tr><td style="background-color:#202b40;padding:24px 32px;">
          <h1 style="margin:0;color:#ffffff;font-size:22px;">{header}</h1>
        </td></tr>
        <tr><td style="padding:32px;">
          <h2 style="color:#202b40;font-size:18px;margin:0 0 16px;">{title}</h2>
          {body_html}
        </td></tr>
        <tr><td style="background-color:#f6f7fa;padding:16px 32px;border-top:1px solid #e5e7eb;">
          <p style="color:#979da8;font-size:11px;margin:0;text-align:center;">
            Powered by {platform} — Deze e-mail is automatisch verstuurd.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def build_lesson_reminder_email(
    student_name: str, lesson_date: str, lesson_time: str
) -> tuple[str, str]:
    subject = f"Herinnering: Les morgen om {lesson_time}"
    body = f"""
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 16px;">
      Beste ouder/verzorger,
    </p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 16px;">
      Dit is een herinnering dat <strong>{escape(student_name)}</strong> morgen
      (<strong>{escape(lesson_date)}</strong>) les heeft om <strong>{escape(lesson_time)}</strong>.
    </p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0;">
      We zien jullie graag!
    </p>"""
    return subject, _base_template("Lesherinnering", body)


def build_absence_alert_email(
    student_name: str, lesson_date: str, status: str
) -> tuple[str, str]:
    status_nl = {
        "absent": "afwezig",
        "sick": "ziek gemeld",
        "excused": "afgemeld",
    }.get(status, status)

    subject = f"Afwezigheidsmelding: {escape(student_name)} was {status_nl}"
    body = f"""
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 16px;">
      Beste ouder/verzorger,
    </p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 16px;">
      Wij willen u laten weten dat <strong>{escape(student_name)}</strong> op
      <strong>{escape(lesson_date)}</strong> als <strong>{status_nl}</strong> is geregistreerd.
    </p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0;">
      Neem contact op als u vragen heeft.
    </p>"""
    return subject, _base_template("Afwezigheidsmelding", body)


def build_schedule_change_email(
    student_name: str,
    original_date: str,
    new_date: str,
    new_time: str,
    reason: str | None = None,
) -> tuple[str, str]:
    subject = f"Roosterwijziging: Les van {escape(student_name)} op {escape(original_date)}"
    reason_html = ""
    if reason:
        reason_html = f"""
        <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 16px;">
          <em>Reden: {escape(reason)}</em>
        </p>"""

    body = f"""
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 16px;">
      Beste ouder/verzorger,
    </p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 16px;">
      De les van <strong>{escape(student_name)}</strong> op <strong>{escape(original_date)}</strong>
      is verplaatst naar <strong>{escape(new_date)}</strong> om <strong>{escape(new_time)}</strong>.
    </p>
    {reason_html}
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0;">
      Excuses voor het ongemak.
    </p>"""
    return subject, _base_template("Roosterwijziging", body)


def build_attendance_report_email(
    period: str, total_lessons: int, present: int, absent: int
) -> tuple[str, str]:
    subject = f"Aanwezigheidsoverzicht {period}"
    body = f"""
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 16px;">
      Beste docent,
    </p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 16px;">
      Hieronder het aanwezigheidsoverzicht voor de periode <strong>{period}</strong>:
    </p>
    <table style="width:100%;border-collapse:collapse;margin:0 0 16px;">
      <tr>
        <td style="padding:8px 12px;border:1px solid #e5e7eb;color:#202b40;font-weight:bold;">Totaal lessen</td>
        <td style="padding:8px 12px;border:1px solid #e5e7eb;color:#767a81;">{total_lessons}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border:1px solid #e5e7eb;color:#202b40;font-weight:bold;">Aanwezig</td>
        <td style="padding:8px 12px;border:1px solid #e5e7eb;color:#22c55e;">{present}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border:1px solid #e5e7eb;color:#202b40;font-weight:bold;">Afwezig</td>
        <td style="padding:8px 12px;border:1px solid #e5e7eb;color:#ef4444;">{absent}</td>
      </tr>
    </table>"""
    return subject, _base_template("Aanwezigheidsoverzicht", body)


def build_invitation_email(
    inviter_name: str,
    org_name: str,
    role: str,
    accept_url: str,
    expire_hours: int,
) -> tuple[str, str]:
    role_nl = {
        "super_admin": "platformbeheerder",
        "org_admin": "beheerder",
        "teacher": "docent",
        "parent": "ouder",
    }.get(role, role)

    subject = f"Uitnodiging: Word {role_nl} bij {org_name}"
    body = f"""
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 16px;">
      Beste,
    </p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 16px;">
      <strong>{escape(inviter_name)}</strong> heeft je uitgenodigd om als <strong>{role_nl}</strong>
      deel te nemen aan <strong>{escape(org_name)}</strong> op {settings.platform_name}.
    </p>
    <table cellpadding="0" cellspacing="0" style="margin:0 auto 24px;">
      <tr><td align="center" style="background-color:#cd095b;border-radius:8px;">
        <a href="{accept_url}" style="display:inline-block;padding:14px 32px;color:#ffffff;text-decoration:none;font-size:15px;font-weight:bold;">
          Uitnodiging accepteren
        </a>
      </td></tr>
    </table>
    <p style="color:#767a81;font-size:13px;line-height:1.5;margin:0 0 8px;">
      Of kopieer deze link in je browser:
    </p>
    <p style="color:#066aab;font-size:13px;word-break:break-all;margin:0 0 24px;">
      {accept_url}
    </p>
    <p style="color:#979da8;font-size:12px;margin:0;">
      Deze uitnodiging is {expire_hours} uur geldig.
    </p>"""
    return subject, _base_template("Uitnodiging", body, header_name=org_name)


def build_password_reset_email(
    full_name: str, reset_url: str, expire_minutes: int
) -> tuple[str, str]:
    subject = f"Wachtwoord resetten — {settings.platform_name}"
    body = f"""
    <p style="color:#202b40;font-size:16px;margin:0 0 16px;">Hallo {escape(full_name)},</p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 24px;">
      We hebben een verzoek ontvangen om je wachtwoord te resetten.
      Klik op de knop hieronder om een nieuw wachtwoord in te stellen.
    </p>
    <table cellpadding="0" cellspacing="0" style="margin:0 auto 24px;">
      <tr><td align="center" style="background-color:#cd095b;border-radius:8px;">
        <a href="{reset_url}" style="display:inline-block;padding:14px 32px;color:#ffffff;text-decoration:none;font-size:15px;font-weight:bold;">
          Wachtwoord resetten
        </a>
      </td></tr>
    </table>
    <p style="color:#767a81;font-size:13px;line-height:1.5;margin:0 0 8px;">
      Of kopieer deze link in je browser:
    </p>
    <p style="color:#066aab;font-size:13px;word-break:break-all;margin:0 0 24px;">
      {reset_url}
    </p>
    <p style="color:#979da8;font-size:12px;margin:0;">
      Deze link is {expire_minutes} minuten geldig.
      Als je geen wachtwoord reset hebt aangevraagd, kun je deze e-mail negeren.
    </p>"""
    return subject, _base_template("Wachtwoord resetten", body)


def build_password_changed_email(full_name: str) -> tuple[str, str]:
    subject = f"Wachtwoord gewijzigd — {settings.platform_name}"
    body = f"""
    <p style="color:#202b40;font-size:16px;margin:0 0 16px;">Hallo {escape(full_name)},</p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0 0 16px;">
      Je wachtwoord voor {settings.platform_name} is zojuist gewijzigd.
    </p>
    <p style="color:#767a81;font-size:14px;line-height:1.6;margin:0;">
      Als je dit niet zelf hebt gedaan, neem dan onmiddellijk contact met ons op.
    </p>"""
    return subject, _base_template("Wachtwoord gewijzigd", body)

"""Password and phone number validation."""

import re

# E.164: + followed by 1-15 digits (country code + subscriber number)
_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def validate_password_strength(password: str) -> str:
    """Validate password meets complexity requirements.

    Rules:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 digit
    - At least 1 special character

    Returns the password if valid, raises ValueError if not.
    """
    if len(password) < 8:
        raise ValueError("Wachtwoord moet minimaal 8 tekens bevatten")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Wachtwoord moet minimaal 1 hoofdletter bevatten")
    if not re.search(r"\d", password):
        raise ValueError("Wachtwoord moet minimaal 1 cijfer bevatten")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Wachtwoord moet minimaal 1 speciaal teken bevatten")
    return password


def validate_phone_e164(phone: str) -> str:
    """Validate phone number is in E.164 format (e.g. +31612345678).

    Returns the normalized phone number if valid, raises ValueError if not.
    """
    normalized = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not _E164_RE.match(normalized):
        raise ValueError(
            "Telefoonnummer moet in internationaal formaat zijn, bijv. +31612345678"
        )
    return normalized

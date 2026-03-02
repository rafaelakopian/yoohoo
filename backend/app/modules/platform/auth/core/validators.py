"""Password complexity validation."""

import re


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

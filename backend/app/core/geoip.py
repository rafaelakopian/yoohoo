"""GeoIP country lookup using MaxMind GeoLite2-Country database.

Provides country-level geolocation for IP addresses. Used in:
- Device fingerprinting (UA + country = unique device context)
- Security alert emails (show login country)
- Session metadata (stored on RefreshToken)

The GeoLite2-Country.mmdb file must be placed in backend/data/.
If the database is missing, all lookups gracefully return None.
"""

import structlog
from pathlib import Path

logger = structlog.get_logger()

_reader = None
_init_attempted = False


def _get_reader():
    """Lazy-load the GeoIP reader singleton."""
    global _reader, _init_attempted

    if _init_attempted:
        return _reader

    _init_attempted = True

    try:
        import geoip2.database
    except ImportError:
        logger.warning("geoip.library_missing", hint="pip install geoip2")
        return None

    # Search paths (Docker: /app/data, dev: backend/data)
    search_paths = [
        Path("/app/data/GeoLite2-Country.mmdb"),
        Path(__file__).resolve().parent.parent.parent / "data" / "GeoLite2-Country.mmdb",
    ]

    for db_path in search_paths:
        if db_path.exists():
            try:
                _reader = geoip2.database.Reader(str(db_path))
                logger.info("geoip.loaded", path=str(db_path))
                return _reader
            except Exception:
                logger.warning("geoip.load_failed", path=str(db_path), exc_info=True)

    logger.info("geoip.database_not_found", searched=[str(p) for p in search_paths])
    return None


def lookup_country(ip_address: str | None) -> str | None:
    """Look up the ISO country code for an IP address.

    Returns 2-letter ISO code (e.g. "NL", "DE", "US") or None if:
    - IP is None/empty/private
    - GeoIP database not available
    - IP not found in database
    """
    if not ip_address or ip_address in ("unknown", "127.0.0.1", "::1"):
        return None

    # Skip private/Docker IPs
    if ip_address.startswith(("10.", "172.16.", "172.17.", "172.18.",
                              "172.19.", "172.20.", "172.21.", "172.22.",
                              "172.23.", "172.24.", "172.25.", "172.26.",
                              "172.27.", "172.28.", "172.29.", "172.30.",
                              "172.31.", "192.168.", "fc", "fd")):
        return None

    reader = _get_reader()
    if not reader:
        return None

    try:
        response = reader.country(ip_address)
        return response.country.iso_code
    except Exception:
        return None


# Country code to Dutch display name mapping
_COUNTRY_NAMES: dict[str, str] = {
    "NL": "Nederland",
    "BE": "België",
    "DE": "Duitsland",
    "FR": "Frankrijk",
    "GB": "Verenigd Koninkrijk",
    "US": "Verenigde Staten",
    "CA": "Canada",
    "AU": "Australië",
    "ES": "Spanje",
    "IT": "Italië",
    "PT": "Portugal",
    "AT": "Oostenrijk",
    "CH": "Zwitserland",
    "SE": "Zweden",
    "NO": "Noorwegen",
    "DK": "Denemarken",
    "PL": "Polen",
    "CZ": "Tsjechië",
    "TR": "Turkije",
    "RU": "Rusland",
    "CN": "China",
    "JP": "Japan",
    "KR": "Zuid-Korea",
    "IN": "India",
    "BR": "Brazilië",
    "MX": "Mexico",
    "ZA": "Zuid-Afrika",
    "UA": "Oekraïne",
    "RO": "Roemenië",
    "HU": "Hongarije",
    "IE": "Ierland",
}


def country_display_name(country_code: str | None) -> str | None:
    """Convert ISO country code to Dutch display name.

    Returns None if country_code is None.
    Falls back to the ISO code itself for unknown countries.
    """
    if not country_code:
        return None
    return _COUNTRY_NAMES.get(country_code.upper(), country_code.upper())

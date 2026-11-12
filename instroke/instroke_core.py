"""Instroke logic that does not depend on Qt or the serial port, so it can be unit-tested.

Covers parsing the Arduino's messages, pricing, VAT, password hashing and
safe updates to the settings file.
"""
import hashlib
import hmac
import json
import os
import secrets

TABLE_COUNT = 24
DEFAULT_VAT_RATE = 0.19
PASSWORD_ITERATIONS = 200_000


def parse_switch_message(raw, table_count=TABLE_COUNT):
    """Parse one line from the Arduino, e.g. b"5 1\\r\\n".

    Returns (table_index, state) with state 1 = table on, 0 = off,
    or None for anything malformed (noise after a reset, half a line, ...).
    """
    text = raw.decode("ascii", errors="ignore").strip()
    parts = text.split()
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return None
    index, state = int(parts[0]), int(parts[1])
    if index >= table_count or state not in (0, 1):
        return None
    return index, state


def cost_for(rate_per_hour, seconds):
    """Price for `seconds` of play at `rate_per_hour`, rounded down to 5 cents."""
    cents = rate_per_hour * max(seconds, 0) / 3600 * 100
    return round(int(cents // 5) * 5 / 100, 2)


def vat_breakdown(gross, vat_rate=DEFAULT_VAT_RATE):
    """Split a gross price (VAT included) into (net, vat).

    The VAT contained in a gross price is gross * rate / (1 + rate),
    e.g. 11.90 EUR at 19 % -> 10.00 net + 1.90 VAT.
    """
    vat = round(gross * vat_rate / (1 + vat_rate), 2)
    return round(gross - vat, 2), vat


def format_duration(seconds):
    """Seconds -> 'HH:MM:SS'; hours keep counting past 24."""
    seconds = int(max(seconds, 0))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def hash_password(password, salt=None, iterations=PASSWORD_ITERATIONS):
    """Return a record to store in the settings file. The password itself is never stored."""
    salt = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return {"salt": salt.hex(), "hash": digest.hex(), "iterations": iterations}


def verify_password(password, record):
    """Check a password against a record from hash_password(), in constant time."""
    if not record:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(record["salt"]), int(record["iterations"])
    )
    return hmac.compare_digest(digest.hex(), record["hash"])


def load_settings(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_settings(path, change):
    """Load the settings, apply change(settings), and write them back.

    Writes to a temporary file first and then replaces the original, so a crash
    or power cut never leaves a half-written settings file behind.
    """
    settings = load_settings(path)
    change(settings)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
    return settings

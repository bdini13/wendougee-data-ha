"""Integration identifiers and conservative polling defaults."""

import hashlib

DOMAIN = "wendougee_data"
SERVICE_CAPTURE_BASELINE = "capture_read_only_baseline"
DEFAULT_POLL_INTERVAL = 30
MIN_POLL_INTERVAL = 10
MAX_POLL_INTERVAL = 300


def device_id(address: str) -> str:
    """Stable within the adapter's address namespace; never expose a raw address."""
    return hashlib.sha256(f"{DOMAIN}:{address.upper()}".encode()).hexdigest()

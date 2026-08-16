import hashlib


def compute_hash(text: str) -> str:
    """SHA-256 hex digest of the given text. Deterministic and fast."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

"""In-memory reset-code store (dev). Production: use email/SMS provider + DB store."""
CODES: dict[str, tuple[str, object]] = {}

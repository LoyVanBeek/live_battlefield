import re
import hmac

_MAX_NAME_LENGTH = 30

_UNSAFE_NAME_RE = re.compile(r"[<>&\"']")


def sanitize_name(name: str | None) -> str:
    """Strip HTML-unsafe characters from a user-supplied display name."""
    if name is None:
        return ""
    return _UNSAFE_NAME_RE.sub("", str(name))[:_MAX_NAME_LENGTH]


def compare_digest_optional(a: str, b: str) -> bool:
    """Constant-time comparison that handles empty secrets gracefully."""
    if not a or not b:
        return False
    return hmac.compare_digest(a, b)

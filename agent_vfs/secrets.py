"""Secret-shape refusal — defense-in-depth, not redaction.

We refuse to write payloads matching obvious credential shapes. This
catches accidental paste-ins; it does NOT defend against an adversary
who knows what the patterns are (they will obfuscate). The point is to
make the human aware before the secret lands in agent memory.
"""
import re


_AWS_ACCESS_KEY = re.compile(r"AKIA[0-9A-Z]{16}")
_GITHUB_PAT = re.compile(r"gh[ps]_[A-Za-z0-9]{36,}")
_JWT = re.compile(
    r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
)


_PATTERNS = (_AWS_ACCESS_KEY, _GITHUB_PAT, _JWT)


def looks_like_secret(text: str) -> bool:
    """Return True if `text` matches any known credential shape."""
    for pat in _PATTERNS:
        if pat.search(text):
            return True
    return False

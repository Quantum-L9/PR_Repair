# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [security]
# tags: [redaction, secrets, masking]
# owner: platform
# status: active
# --- /L9_META ---

"""Best-effort secret redaction.

Used before untrusted text (e.g. verification stderr) is forwarded to an external
model or logged. Not a guarantee -- it masks common, high-signal secret shapes so
tokens/credentials in build output don't leak to the router.
"""

from __future__ import annotations

import re

_REDACTED = "***REDACTED***"

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # credentials embedded in URLs: https://user:pass@host -> https://***:***@host
    (re.compile(r"(https?://)[^:/\s@]+:[^@/\s]+@"), r"\1***:***@"),
    # Authorization / Bearer headers
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"), "Bearer " + _REDACTED),
    # key: value / KEY=value where the key name looks sensitive
    (
        re.compile(r"(?i)\b([A-Za-z0-9_]*(?:token|api[_-]?key|secret|password|passwd|credential)[A-Za-z0-9_]*)\b(\s*[:=]\s*)\S+"),
        r"\1\2" + _REDACTED,
    ),
    # well-known token prefixes (GitHub, OpenAI/OpenRouter, Slack, AWS, Google)
    (
        re.compile(
            r"\b("
            r"gh[pousr]_[A-Za-z0-9]{16,}"
            r"|github_pat_[A-Za-z0-9_]{20,}"
            r"|sk-[A-Za-z0-9]{16,}"
            r"|xox[baprs]-[A-Za-z0-9-]{10,}"
            r"|AKIA[0-9A-Z]{16}"
            r"|AIza[0-9A-Za-z\-_]{20,}"
            r")\b"
        ),
        _REDACTED,
    ),
]


def redact_secrets(text: str) -> str:
    """Mask common secret shapes in ``text``. Best-effort, never raises."""
    redacted = text
    for pattern, replacement in _PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted

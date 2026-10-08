"""Secret hygiene for server logs: tokens and keys must never land in files.

Access logs echo full request lines (`POST /mcp?token=...`), so every
installed logger passes through `scrub()` first. Add new secret-bearing
parameter names to _SECRET_PARAMS, never new loggers without the filter.
"""
from __future__ import annotations

import logging
import re

_SECRET_PARAMS = ("token", "api_key", "owner_sig", "auth")
_PATTERN = re.compile(
    r"([?&](?:" + "|".join(_SECRET_PARAMS) + r")=)[^&\s\"']*")


def scrub(text: str) -> str:
    """Redact secret query values, keeping the parameter name for debugging."""
    return _PATTERN.sub(r"\1REDACTED", str(text))


class _ScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Scrub string ARGS, never the template and never non-strings:
        # replacing msg breaks lazy formatters, and str()-ing ints breaks
        # %d status codes (uvicorn access). Both failure modes leak raw
        # values through logging's own error report.
        try:
            args = record.args
            if isinstance(args, dict):
                record.args = {k: (scrub(v) if isinstance(v, str) else v)
                               for k, v in args.items()}
            elif isinstance(args, (tuple, list)):
                record.args = type(args)(
                    (scrub(a) if isinstance(a, str) else a) for a in args)
            elif isinstance(args, str):
                record.args = scrub(args)
        except Exception:
            pass
        return True


def install(*logger_names: str) -> None:
    for name in logger_names:
        logging.getLogger(name).addFilter(_ScrubFilter())

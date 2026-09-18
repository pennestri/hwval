"""Demo: severity levels control whether a check raises or just logs.

Severity map (UVVM-style):

    TB_FAILURE  / FAILURE   -> log CRITICAL, raise AssertionError
    TB_ERROR    / ERROR     -> log ERROR,     raise AssertionError
    TB_WARNING  / WARNING   -> log WARNING,   no raise
    NOTE        / INFO      -> log INFO,      no raise
    DEBUG       / LOGICAL   -> log DEBUG,     no raise
"""

from __future__ import annotations

import logging
import sys

from hwval import AlertLevel, check_value

# Configure the root logger so we can SEE the log output in this demo.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)


def demo(label: str, level: AlertLevel, value: int, exp: int) -> bool | None:
    """Run one check at the given level and return its result."""
    print(f"\n[{label}] {level.value} ({value!r} vs {exp!r})")
    try:
        result = check_value(value, exp, alert_level=level, msg=label)
        print(f"  -> returned {result}")
        return result
    except AssertionError as exc:
        print(f"  -> raised AssertionError: {exc}")
        return None


def main() -> None:
    # ERROR-class: raises on failure.
    demo("hard-mismatch", AlertLevel.ERROR, 1, 2)

    # WARNING-class: returns False on failure.
    demo("soft-mismatch", AlertLevel.WARNING, 1, 2)

    # NOTE-class: just an info log, always returns the actual pass/fail.
    demo("info-only", AlertLevel.NOTE, 1, 2)

    # All-severity passing case (no raise, no log spam).
    demo("ok-everywhere", AlertLevel.WARNING, 42, 42)

    print("\n03_severity_levels: all demos ran.")


if __name__ == "__main__":
    main()
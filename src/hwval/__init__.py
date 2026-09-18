"""Bare-minimum Python port of UVVM's check family.

See: https://uvvm.github.io/utility_library.html#checks-and-awaits

Only the `check_value` / `check_value_in_range` family is ported.
`check_stable`, `await_*` need VHDL simulation time — left as stubs.
"""

from .checks import (
    AlertLevel,
    CheckRecord,
    MatchStrictness,
    Radix,
    TestSummary,
    check_value,
    check_value_in_range,
    current_summary,
    report_test_summary,
    reset_test_summary,
    set_logger,
)

__all__ = [
    "AlertLevel",
    "CheckRecord",
    "MatchStrictness",
    "Radix",
    "SegDocument",
    "TestSummary",
    "check_value",
    "check_value_in_range",
    "current_summary",
    "report_test_summary",
    "reset_test_summary",
    "set_logger",
]

# `SegDocument` lives in the optional `hwval.docs` submodule; importing
# it eagerly would force a docxtpl dependency on every user, so the name
# is exposed lazily.
try:
    from .docs import SegDocument  # noqa: F401
except ImportError:  # pragma: no cover - optional extra missing
    pass

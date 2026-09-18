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
    report_test_summary,
    reset_test_summary,
    set_logger,
)

__all__ = [
    "AlertLevel",
    "CheckRecord",
    "MatchStrictness",
    "Radix",
    "TestSummary",
    "check_value",
    "check_value_in_range",
    "report_test_summary",
    "reset_test_summary",
    "set_logger",
]

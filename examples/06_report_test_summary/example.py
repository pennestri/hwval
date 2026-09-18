"""Demo: ``report_test_summary`` — summarise WARNING checks.

Every `check_value` / `check_value_in_range` call at `WARNING` or
`TB_WARNING` severity is accumulated in module state. `report_test_summary`
prints (and returns) a structured summary, then clears the accumulator.
"""

from __future__ import annotations

import io

from hwval import (
    AlertLevel,
    check_value,
    check_value_in_range,
    report_test_summary,
    reset_test_summary,
)


def main() -> None:
    reset_test_summary()  # start with a clean accumulator

    # 1. Mix of passing and failing WARNING checks.
    check_value(0, 0, alert_level=AlertLevel.WARNING, msg="REG0 OK",
                scope="reg_walk", msg_id="ID_REG0")
    check_value(1, 2, alert_level=AlertLevel.WARNING, msg="REG1 drift",
                scope="reg_walk", msg_id="ID_REG1")
    check_value(3, 3, alert_level=AlertLevel.WARNING, msg="REG2 OK",
                scope="reg_walk", msg_id="ID_REG2")
    check_value_in_range(50, 10, 100,
                         alert_level=AlertLevel.WARNING, msg="REG3 range")
    check_value_in_range(500, 10, 100,
                         alert_level=AlertLevel.WARNING, msg="REG4 range")

    # 2. ERROR-class checks are NOT accumulated (they raise instead).
    try:
        check_value(9, 8, msg="hard fail")
    except AssertionError:
        pass

    # 3. Render the summary to a string so we control what's printed.
    buf = io.StringIO()
    summary = report_test_summary(file=buf)
    print(buf.getvalue(), end="")

    # 4. Inspect the structured result.
    print(f"structured counts: passed={summary.passed_count} "
          f"failed={summary.failed_count} ok={summary.ok}")

    # 5. After report, the accumulator is empty by default.
    empty_buf = io.StringIO()
    empty = report_test_summary(file=empty_buf)
    print(f"\nafter reset: {empty_buf.getvalue().strip()!r} "
          f"(total={empty.total})")

    print("\n06_report_test_summary: all demos ran.")


if __name__ == "__main__":
    main()
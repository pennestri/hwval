"""Demo: ``check_value_in_range`` basics.

Inclusive range check: ``min_value <= value <= max_value``. Same severity /
log / raise behaviour as ``check_value``.
"""

from __future__ import annotations

from hwval import AlertLevel, check_value_in_range


def main() -> None:
    # 1. Inside the range -> True.
    assert check_value_in_range(50, 10, 100, msg="inside") is True

    # 2. Boundary values are inclusive.
    assert check_value_in_range(10, 10, 100, msg="lower bound") is True
    assert check_value_in_range(100, 10, 100, msg="upper bound") is True

    # 3. Out-of-range WARNING -> returns False, no raise.
    assert (
        check_value_in_range(
            150,
            10,
            100,
            alert_level=AlertLevel.WARNING,
            msg="too high (soft)",
        )
        is False
    )

    # 4. Out-of-range ERROR -> raises AssertionError.
    try:
        check_value_in_range(0, 10, 100, msg="too low (hard)")
    except AssertionError as exc:
        print(f"ERROR raised as expected: {exc}")

    # 5. Real-world ADC sample check.
    sample = 2_750
    check_value_in_range(
        sample,
        min_value=2_000,
        max_value=3_000,
        msg="ADC sample must fall in the expected band",
        scope="adc_checker",
        msg_id="ID_ADC_BAND",
    )

    print("02_check_value_in_range: all demos ran.")


if __name__ == "__main__":
    main()
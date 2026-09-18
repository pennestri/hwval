"""Demo: ``check_value`` basics.

Compares ``value`` to ``exp``. Returns ``True`` on pass, ``False`` on fail;
``ERROR``/``*_FAILURE`` severities also raise ``AssertionError``.

Sequence inputs (list/tuple) are compared element-wise.
"""

from __future__ import annotations

from hwval import AlertLevel, Radix, check_value


def main() -> None:
    # 1. Pass at default (ERROR) severity.
    assert check_value(42, 42, msg="int match") is True

    # 2. Pass with scope, msg_id and hex radix for tagged logs.
    assert (
        check_value(
            0xDEAD_BEEF,
            0xDEAD_BEEF,
            msg="REG32 readback",
            scope="reg_model",
            msg_id="ID_REG_RD",
            radix=Radix.HEX,
        )
        is True
    )

    # 3. Failing WARNING check returns False (no raise).
    assert (
        check_value(1, 2, alert_level=AlertLevel.WARNING, msg="drift") is False
    )

    # 4. Failing ERROR check raises AssertionError.
    try:
        check_value(1, 2, msg="hard fail")
    except AssertionError as exc:
        print(f"ERROR raised as expected: {exc}")

    # 5. Sequence comparison (byte vector).
    assert (
        check_value([0xDE, 0xAD], [0xDE, 0xAD], msg="vector", radix=Radix.HEX)
        is True
    )

    print("01_check_value: all demos ran.")


if __name__ == "__main__":
    main()
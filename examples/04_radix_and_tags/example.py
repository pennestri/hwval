"""Demo: log-tag kwargs (`scope`, `msg_id`, `msg`) and `radix` formatting.

All checks log to ``logging.getLogger("hwval")``. This example attaches a
capturing handler so we can show the formatted log record for each call.
"""

from __future__ import annotations

import logging

from hwval import MatchStrictness, Radix, check_value, set_logger


def main() -> None:
    # Capturing handler so we can show log lines in the demo.
    captured: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(self.format(record))

    handler = Capture(level=logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger = logging.getLogger("hwval")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    set_logger(logger)

    # 1. Default radix: HEX_BIN_IF_INVALID picks hex/bin depending on the
    #    value's type. Plain ints render as decimal.
    check_value(42, 42, msg="decimal radix")

    # 2. Force HEX.
    check_value(0x2A, 0x2A, msg="explicit hex", radix=Radix.HEX)

    # 3. Force BIN.
    check_value(0b101010, 0b101010, msg="explicit bin", radix=Radix.BIN)

    # 4. Sequence with HEX (joined without separators).
    check_value([0xDE, 0xAD], [0xDE, 0xAD], msg="vector hex", radix=Radix.HEX)

    # 5. Tagged with scope + msg_id.
    check_value(
        0xCAFE,
        0xCAFE,
        msg="REG16 readback",
        scope="reg_model",
        msg_id="ID_REG16",
        radix=Radix.HEX,
    )

    # 6. UVVM-style positional MatchStrictness.
    check_value(7, 7, MatchStrictness.MATCH_EXACT, msg="strict match")

    print("\n--- captured log records ---")
    for line in captured:
        print(line)

    print("\n04_radix_and_tags: all demos ran.")


if __name__ == "__main__":
    main()
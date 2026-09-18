"""Demo: capturing log output and replacing the module logger.

All checks log to ``logging.getLogger("hwval")``. This example:

  1. Uses pytest-style ``caplog`` to assert on log content (uncomment the
     bottom block to run under pytest).
  2. Replaces the module logger with one from a host application via
     ``set_logger``.

Both blocks are runnable from the CLI to show the visible effect.
"""

from __future__ import annotations

import logging
import sys

from hwval import AlertLevel, check_value, set_logger


def main() -> None:
    print("=== block 1: capturing log records via a custom handler ===")
    captured: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler = Capture(level=logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    hwval_logger = logging.getLogger("hwval")
    hwval_logger.setLevel(logging.DEBUG)
    hwval_logger.addHandler(handler)

    check_value(
        1,
        2,
        alert_level=AlertLevel.WARNING,
        msg="captured",
        scope="demo",
        msg_id="ID_DEMO",
    )

    assert len(captured) == 1, f"expected 1 record, got {len(captured)}"
    rec = captured[0]
    assert rec.levelno == logging.WARNING
    assert "captured" in rec.getMessage()
    assert "demo" in rec.getMessage()
    assert "ID_DEMO" in rec.getMessage()
    print(f"  captured: {rec.getMessage()}")
    hwval_logger.removeHandler(handler)

    print("\n=== block 2: replacing the module logger via set_logger ===")
    host_logger = logging.getLogger("my_app.hwval")
    host_logger.setLevel(logging.INFO)
    # Make sure messages propagate up so they actually print here.
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    set_logger(host_logger)

    check_value(99, 99, msg="now routed to my_app.hwval")

    print("\n05_logging: all demos ran.")


if __name__ == "__main__":
    main()
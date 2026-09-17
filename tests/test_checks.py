"""Tests for hwval. Run with: uv run pytest"""

from __future__ import annotations

import logging
import unittest

from hwval import (
    AlertLevel,
    MatchStrictness,
    Radix,
    check_value,
    check_value_in_range,
    set_logger,
)


class CapturingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class UvvmCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handler = CapturingHandler()
        logger = logging.getLogger("hwval")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(self.handler)
        set_logger(logger)

    def tearDown(self) -> None:
        logging.getLogger("hwval").removeHandler(self.handler)

    # ---- check_value ----------------------------------------------------- #

    def test_check_value_pass_returns_true(self):
        self.assertTrue(check_value(42, 42, msg="int match"))

    def test_check_value_fail_returns_false_at_warning(self):
        self.assertFalse(
            check_value(1, 2, alert_level=AlertLevel.WARNING, msg="warn mismatch")
        )
        # one record, level WARNING, no exception
        self.assertEqual(len(self.handler.records), 1)
        self.assertEqual(self.handler.records[0].levelno, logging.WARNING)

    def test_check_value_fail_raises_at_error(self):
        with self.assertRaises(AssertionError):
            check_value(1, 2, msg="must raise")
        self.assertEqual(self.handler.records[0].levelno, logging.ERROR)

    def test_check_value_fail_raises_at_tb_failure(self):
        with self.assertRaises(AssertionError):
            check_value("a", "b", alert_level=AlertLevel.TB_FAILURE, msg="fatal")

    def test_check_value_msg_id_and_scope_logged(self):
        check_value(0, 0, msg="tagged", scope="my_scope", msg_id="ID_FOO")
        rec = self.handler.records[0]
        self.assertIn("my_scope", rec.getMessage())
        self.assertIn("ID_FOO", rec.getMessage())

    def test_check_value_hex_radix_in_message(self):
        check_value(0x2A, 0x2A, msg="hex", radix=Radix.HEX)
        self.assertIn("0x2A", self.handler.records[0].getMessage())

    def test_check_value_sequence_with_hex(self):
        check_value([0xDE, 0xAD], [0xDE, 0xAD], msg="seq", radix=Radix.HEX)
        self.assertIn("0xDE", self.handler.records[0].getMessage())

    def test_check_value_positional_match_strictness(self):
        # UVVM-style: pass MatchStrictness as positional arg.
        self.assertTrue(
            check_value(
                7,
                7,
                MatchStrictness.MATCH_EXACT,
                msg="strict pass",
            )
        )
        self.assertIn("MATCH_EXACT", self.handler.records[0].getMessage())

    def test_check_value_rejects_unexpected_positional(self):
        with self.assertRaises(TypeError):
            check_value(1, 1, "extra")

    # ---- check_value_in_range ------------------------------------------- #

    def test_range_inside(self):
        self.assertTrue(check_value_in_range(50, 10, 100, msg="inside"))

    def test_range_below_raises(self):
        with self.assertRaises(AssertionError):
            check_value_in_range(5, 10, 100, msg="too low")

    def test_range_above_warns_only(self):
        self.assertFalse(
            check_value_in_range(
                200, 10, 100, alert_level=AlertLevel.WARNING, msg="too high"
            )
        )

    def test_range_boundary_inclusive(self):
        self.assertTrue(check_value_in_range(10, 10, 100))
        self.assertTrue(check_value_in_range(100, 10, 100))

    # ---- stubs ----------------------------------------------------------- #

    def test_hw_time_stubs_raise(self):
        from hwval.checks import check_stable, await_change, await_value
        for fn in (check_stable, await_change, await_value):
            with self.subTest(fn=fn.__name__):
                with self.assertRaises(NotImplementedError):
                    fn()


if __name__ == "__main__":
    unittest.main()

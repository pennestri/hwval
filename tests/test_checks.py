"""Tests for hwval. Run with: uv run pytest"""

from __future__ import annotations

import io
import logging
import unittest

from hwval import (
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
        reset_test_summary()

    def tearDown(self) -> None:
        logging.getLogger("hwval").removeHandler(self.handler)
        reset_test_summary()

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

    # ---- report_test_summary -------------------------------------------- #

    def test_warning_passing_check_is_recorded(self):
        check_value(7, 7, alert_level=AlertLevel.WARNING, msg="ok")
        summary = report_test_summary(file=io.StringIO())
        self.assertEqual(summary.passed_count, 1)
        self.assertEqual(summary.failed_count, 0)
        self.assertTrue(summary.ok)
        self.assertEqual(summary.total, 1)
        self.assertEqual(len(summary.passed), 1)
        self.assertIsInstance(summary.passed[0], CheckRecord)
        self.assertEqual(summary.passed[0].msg, "ok")
        self.assertTrue(summary.passed[0].passed)

    def test_warning_failing_check_is_recorded(self):
        check_value(1, 2, alert_level=AlertLevel.WARNING, msg="bad")
        summary = report_test_summary(file=io.StringIO())
        self.assertEqual(summary.failed_count, 1)
        self.assertEqual(summary.passed_count, 0)
        self.assertFalse(summary.ok)
        self.assertEqual(summary.failed[0].msg, "bad")
        self.assertFalse(summary.failed[0].passed)

    def test_tb_warning_alias_also_tracked(self):
        check_value(1, 2, alert_level=AlertLevel.TB_WARNING, msg="tb warn")
        summary = report_test_summary(file=io.StringIO())
        self.assertEqual(summary.failed_count, 1)

    def test_error_level_checks_are_not_tracked(self):
        # ERROR raises and must not pollute the summary.
        with self.assertRaises(AssertionError):
            check_value(1, 2, alert_level=AlertLevel.ERROR, msg="err")
        summary = report_test_summary(file=io.StringIO())
        self.assertEqual(summary.total, 0)

    def test_note_and_info_levels_are_not_tracked(self):
        # Only WARNING / TB_WARNING are accumulated by default.
        check_value(1, 2, alert_level=AlertLevel.NOTE, msg="n")
        check_value(1, 2, alert_level=AlertLevel.INFO, msg="i")
        check_value(1, 2, alert_level=AlertLevel.DEBUG, msg="d")
        summary = report_test_summary(file=io.StringIO())
        self.assertEqual(summary.total, 0)

    def test_range_warning_checks_are_tracked(self):
        check_value_in_range(200, 10, 100, alert_level=AlertLevel.WARNING, msg="too high")
        check_value_in_range(50, 10, 100, alert_level=AlertLevel.WARNING, msg="inside")
        summary = report_test_summary(file=io.StringIO())
        self.assertEqual(summary.failed_count, 1)
        self.assertEqual(summary.passed_count, 1)

    def test_report_resets_by_default(self):
        check_value(1, 2, alert_level=AlertLevel.WARNING, msg="once")
        first = report_test_summary(file=io.StringIO())
        self.assertEqual(first.total, 1)
        second = report_test_summary(file=io.StringIO())
        self.assertEqual(second.total, 0)

    def test_report_keeps_state_when_reset_false(self):
        check_value(1, 2, alert_level=AlertLevel.WARNING, msg="once")
        first = report_test_summary(file=io.StringIO(), reset=False)
        self.assertEqual(first.total, 1)
        second = report_test_summary(file=io.StringIO(), reset=False)
        self.assertEqual(second.total, 1)
        # finally clean up
        reset_test_summary()

    def test_reset_test_summary_clears_accumulator(self):
        check_value(1, 2, alert_level=AlertLevel.WARNING, msg="x")
        reset_test_summary()
        summary = report_test_summary(file=io.StringIO())
        self.assertEqual(summary.total, 0)

    def test_report_fail_on_failed_raises(self):
        check_value(1, 2, alert_level=AlertLevel.WARNING, msg="boom")
        with self.assertRaises(AssertionError):
            report_test_summary(file=io.StringIO(), fail_on_failed=True)

    def test_report_fail_on_failed_passes_when_clean(self):
        check_value(7, 7, alert_level=AlertLevel.WARNING, msg="ok")
        # Should not raise.
        summary = report_test_summary(
            file=io.StringIO(), fail_on_failed=True
        )
        self.assertTrue(summary.ok)

    def test_report_prints_to_provided_file(self):
        check_value(1, 2, alert_level=AlertLevel.WARNING, msg="bad")
        check_value(7, 7, alert_level=AlertLevel.WARNING, msg="good")
        buf = io.StringIO()
        report_test_summary(file=buf)
        text = buf.getvalue()
        self.assertIn("Test Summary: 1 passed, 1 failed", text)
        self.assertIn("FAILED (1):", text)
        self.assertIn("PASSED (1):", text)
        self.assertIn("bad", text)
        self.assertIn("good", text)

    def test_record_carries_scope_msg_id_detail(self):
        check_value(
            1, 2,
            alert_level=AlertLevel.WARNING,
            msg="drift",
            scope="counter",
            msg_id="ID_DRIFT",
            radix=Radix.DEC,
        )
        summary = report_test_summary(file=io.StringIO())
        rec = summary.failed[0]
        self.assertEqual(rec.scope, "counter")
        self.assertEqual(rec.msg_id, "ID_DRIFT")
        self.assertEqual(rec.msg, "drift")
        self.assertIn("value=1", rec.detail)
        self.assertIn("expected=2", rec.detail)


if __name__ == "__main__":
    unittest.main()

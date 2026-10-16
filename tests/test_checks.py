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
    get_test_id_function,
    report_test_summary,
    reset_test_summary,
    set_logger,
    set_test_id_function,
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
        # Always restore the default test_id function so tests are
        # independent of whatever the previous test left installed.
        set_test_id_function()

    def tearDown(self) -> None:
        logging.getLogger("hwval").removeHandler(self.handler)
        reset_test_summary()
        set_test_id_function()

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

    # ---- test_id machinery --------------------------------------------- #

    def test_default_test_id_is_sequential(self):
        check_value(1, 1, alert_level=AlertLevel.WARNING, msg="a")
        check_value(2, 2, alert_level=AlertLevel.WARNING, msg="b")
        check_value(3, 3, alert_level=AlertLevel.WARNING, msg="c")
        s = report_test_summary(file=io.StringIO())
        self.assertEqual([r.test_id for r in s.passed],
                         ["TID_0001", "TID_0002", "TID_0003"])

    def test_test_id_function_receives_record_and_seq(self):
        seen: list[tuple] = []

        def my_fn(record, seq):
            seen.append((record.scope, record.msg_id, record.passed, seq))
            return f"X_{seq}"

        set_test_id_function(my_fn)
        check_value(1, 1, alert_level=AlertLevel.WARNING,
                    msg="a", scope="S", msg_id="M")
        check_value(1, 2, alert_level=AlertLevel.WARNING,
                    msg="b", scope="T", msg_id="N")
        s = report_test_summary(file=io.StringIO())
        # seq is 1-indexed and 0..2
        self.assertEqual(
            seen,
            [("S", "M", True, 1), ("T", "N", False, 2)],
        )
        self.assertEqual([r.test_id for r in (s.passed + s.failed)],
                         ["X_1", "X_2"])

    def test_test_id_function_return_value_is_coerced_to_str(self):
        set_test_id_function(lambda rec, seq: seq)  # returns int
        check_value(1, 1, alert_level=AlertLevel.WARNING, msg="a")
        s = report_test_summary(file=io.StringIO())
        self.assertEqual(s.passed[0].test_id, "1")

    def test_test_id_function_falls_back_on_exception(self):
        def bad(record, seq):
            raise RuntimeError("nope")

        set_test_id_function(bad)
        # The check should still be recorded; the function failure must
        # not corrupt the WARNING accumulator.
        check_value(1, 1, alert_level=AlertLevel.WARNING, msg="still-works")
        s = report_test_summary(file=io.StringIO())
        self.assertEqual(s.passed_count, 1)
        # Fallback default is the sequential function.
        self.assertEqual(s.passed[0].test_id, "TID_0001")

    def test_set_test_id_function_none_restores_default(self):
        set_test_id_function(lambda r, s: "manual")
        check_value(1, 1, alert_level=AlertLevel.WARNING, msg="manual")
        set_test_id_function()
        # Re-stamping kicks in: the existing record's test_id is
        # re-derived using the (now default) function, so 'manual' is
        # replaced by the sequential default.
        check_value(2, 2, alert_level=AlertLevel.WARNING, msg="default")
        s = report_test_summary(file=io.StringIO())
        # Re-stamped first record + freshly stamped second record.
        self.assertEqual(
            [r.test_id for r in (s.passed + s.failed)],
            ["TID_0001", "TID_0002"],
        )

    def test_get_test_id_function_returns_callable(self):
        fn = get_test_id_function()
        self.assertTrue(callable(fn))
        # Default behavior until overridden.
        check_value(1, 1, alert_level=AlertLevel.WARNING, msg="x")
        s = report_test_summary(file=io.StringIO())
        self.assertEqual(s.passed[0].test_id, "TID_0001")

    def test_reset_test_summary_resets_test_id_sequence(self):
        check_value(1, 1, alert_level=AlertLevel.WARNING, msg="a")
        check_value(2, 2, alert_level=AlertLevel.WARNING, msg="b")
        s1 = report_test_summary(file=io.StringIO())
        self.assertEqual(s1.passed[0].test_id, "TID_0001")
        self.assertEqual(s1.passed[1].test_id, "TID_0002")

        check_value(3, 3, alert_level=AlertLevel.WARNING, msg="c")
        s2 = report_test_summary(file=io.StringIO())
        # Sequence restarts at 1 after a reset (which report_test_summary
        # performs by default).
        self.assertEqual(s2.passed[0].test_id, "TID_0001")

    def test_error_level_does_not_consume_test_id_seq(self):
        # ERROR is not tracked, so its counter increment must be skipped
        # to keep WARNING seqs contiguous.
        with self.assertRaises(AssertionError):
            check_value(1, 2, alert_level=AlertLevel.ERROR, msg="raise")
        check_value(1, 1, alert_level=AlertLevel.WARNING, msg="ok")
        s = report_test_summary(file=io.StringIO())
        self.assertEqual(s.passed[0].test_id, "TID_0001")

    def test_checkrecord_test_id_defaults_to_empty(self):
        # Backward-compat: existing code that builds a CheckRecord
        # without test_id still works.
        rec = CheckRecord(
            scope="s", msg_id="i", msg="m",
            passed=True, detail="d",
        )
        self.assertEqual(rec.test_id, "")

    def test_checkrecord_accepts_test_id(self):
        rec = CheckRecord(
            scope="s", msg_id="i", msg="m",
            passed=True, detail="d", test_id="TID_42",
        )
        self.assertEqual(rec.test_id, "TID_42")

    # ---- extras (YML-declared user fields) ---------------------------- #

    def test_extras_kwargs_land_on_record(self):
        check_value(
            1, 1, alert_level=AlertLevel.WARNING, msg="x",
            operator="alice", notes="re-checked",
        )
        s = report_test_summary(file=io.StringIO())
        self.assertEqual(
            s.passed[0].extras,
            {"operator": "alice", "notes": "re-checked"},
        )

    def test_extras_kwargs_work_with_check_value_in_range(self):
        check_value_in_range(
            50, 10, 100, alert_level=AlertLevel.WARNING, msg="y",
            operator="bob",
        )
        s = report_test_summary(file=io.StringIO())
        self.assertEqual(s.passed[0].extras, {"operator": "bob"})

    def test_extras_default_to_empty_dict(self):
        # No kwargs at all → no extras.
        check_value(1, 1, alert_level=AlertLevel.WARNING, msg="z")
        s = report_test_summary(file=io.StringIO())
        self.assertEqual(s.passed[0].extras, {})

    def test_extras_preserved_across_dataclass_copy(self):
        # _emit uses dataclasses.replace to set test_id; the extras
        # dict must survive that copy.
        check_value(
            1, 1, alert_level=AlertLevel.WARNING, msg="x",
            operator="alice",
        )
        s = report_test_summary(file=io.StringIO())
        self.assertEqual(s.passed[0].extras, {"operator": "alice"})

    def test_extras_isolation_between_records(self):
        # Mutating one record's extras must never leak into another.
        check_value(1, 1, alert_level=AlertLevel.WARNING, msg="a", tag="A")
        check_value(2, 2, alert_level=AlertLevel.WARNING, msg="b", tag="B")
        s = report_test_summary(file=io.StringIO())
        self.assertEqual(s.passed[0].extras, {"tag": "A"})
        self.assertEqual(s.passed[1].extras, {"tag": "B"})

    def test_extras_accepts_non_string_values(self):
        # The library stores whatever the user passes; the report
        # formatter decides how to render it.
        check_value(
            1, 1, alert_level=AlertLevel.WARNING, msg="x",
            address=0xDEAD, retries=3,
        )
        s = report_test_summary(file=io.StringIO())
        self.assertEqual(
            s.passed[0].extras,
            {"address": 0xDEAD, "retries": 3},
        )

    def test_checkrecord_extras_default_is_empty_dict(self):
        # Backward-compat: CheckRecord can still be built without
        # passing extras.
        rec = CheckRecord(
            scope="s", msg_id="i", msg="m",
            passed=True, detail="d",
        )
        self.assertEqual(rec.extras, {})

    # ---- value / expected on CheckRecord ------------------------------ #

    def test_checkrecord_stores_value_and_expected(self):
        check_value(
            1, 2,
            alert_level=AlertLevel.WARNING,
            msg="drift", scope="counter", msg_id="ID_DRIFT",
        )
        s = report_test_summary(file=io.StringIO())
        rec = s.failed[0]
        self.assertEqual(rec.value, 1)
        self.assertEqual(rec.expected, 2)

    def test_checkrecord_value_expected_for_range_check(self):
        check_value_in_range(
            50, 10, 100,
            alert_level=AlertLevel.WARNING, msg="inside",
        )
        s = report_test_summary(file=io.StringIO())
        rec = s.passed[0]
        self.assertEqual(rec.value, 50)
        # Range checks expose the bounds as a literal "in [min, max]"
        # string — matches what report_test_summary would show.
        self.assertEqual(rec.expected, "in [10, 100]")

    def test_checkrecord_value_expected_default_to_none(self):
        # Constructing without value/expected is fine (the user's
        # spec: pass them with defaults so you can build a "marker"
        # record without them).
        rec = CheckRecord(scope="s", msg_id="i", msg="m")
        self.assertIsNone(rec.value)
        self.assertIsNone(rec.expected)

    def test_checkrecord_passed_defaults_to_true(self):
        # "no failure has been reported" wins by default. Avoids
        # silent mis-classification of a marker-only record as a
        # failure.
        rec = CheckRecord(scope="s", msg_id="i", msg="m")
        self.assertIs(rec.passed, True)

    def test_checkrecord_value_field_survives_emit(self):
        # Sanity: building via check_value (which goes through
        # _emit) populates value + expected.
        check_value(0xDEAD, 0xBEEF, alert_level=AlertLevel.WARNING,
                    msg="x")
        s = report_test_summary(file=io.StringIO())
        self.assertEqual(s.failed[0].value, 0xDEAD)
        self.assertEqual(s.failed[0].expected, 0xBEEF)

    def test_checkrecord_accepts_value_and_expected_in_constructor(self):
        rec = CheckRecord(
            scope="s", msg_id="i", msg="m",
            value=42, expected=43,
        )
        self.assertEqual(rec.value, 42)
        self.assertEqual(rec.expected, 43)


if __name__ == "__main__":
    unittest.main()

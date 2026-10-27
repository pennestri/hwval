"""Tests for hwval.docs (SegDocument). Run with: uv run pytest

Requires the optional `hwval[docs]` extra (docxtpl, python-docx, jinja2).
"""

from __future__ import annotations

import io
import unittest
from pathlib import Path

# Guard the whole module on the optional extra.
try:
    from docxtpl import DocxTemplate  # noqa: F401
    HAS_DOCXTPL = True
except ImportError:  # pragma: no cover - depends on optional extra
    HAS_DOCXTPL = False

try:
    import yaml  # noqa: F401
    HAS_YAML = True
except ImportError:  # pragma: no cover - depends on optional extra
    HAS_YAML = False


from hwval import (  # noqa: E402  (after the optional guard)
    AlertLevel,
    CheckRecord,
    Radix,
    TestSummary,
    check_value,
    current_summary,
    reset_test_summary,
)


def _make_template(path: Path, body_paragraphs: list[str]) -> None:
    """Write a tiny docx with one paragraph per entry.

    docxtpl's ``{%p ... %}`` tags must sit on a paragraph of their own.
    Each entry in ``body_paragraphs`` becomes one paragraph in the
    rendered document.
    """
    from docx import Document

    doc = Document()
    for text in body_paragraphs:
        doc.add_paragraph(text)
    doc.save(path)


def _read_paragraphs(path: Path) -> list[str]:
    from docx import Document

    doc = Document(str(path))
    return [p.text for p in doc.paragraphs]


@unittest.skipUnless(HAS_DOCXTPL, "requires hwval[docs] extra (docxtpl)")
class SegDocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # Keep tests independent: any YML-driven test_id_function
        # install in this test must not leak to the next.
        from hwval import get_test_id_function, set_test_id_function
        self._prev_tid_fn = get_test_id_function()
        set_test_id_function()
        self.addCleanup(set_test_id_function, self._prev_tid_fn)

        # Two minimal templates: "test performed" lists records that ran,
        # "test results" lists failed records with their detail line.
        # docxtpl requires each {%p %} tag on its own paragraph.
        self.test_template = self.root / "test_performed.docx"
        self.results_template = self.root / "test_results.docx"
        _make_template(
            self.test_template,
            [
                "Performed: {{ summary.total }}",
                "{%p for rec in records %}",
                "{{ rec.msg }}|",
                "{%p endfor %}",
            ],
        )
        _make_template(
            self.results_template,
            [
                "Total {{ summary.total }}, {{ summary.failed_count }} failed",
                "{%p for rec in failed %}",
                "{{ rec.msg }}#",
                "{%p endfor %}",
            ],
        )

        # Pre-populate the accumulator so `_generate()` has data.
        reset_test_summary()
        check_value(
            1, 1, alert_level=AlertLevel.WARNING,
            msg="REG0 readback", scope="reg_walk", msg_id="ID_REG0",
        )
        check_value(
            2, 3, alert_level=AlertLevel.WARNING,
            msg="REG1 readback", scope="reg_walk", msg_id="ID_REG1",
        )
        check_value(
            0xFF, 0xFF, alert_level=AlertLevel.WARNING,
            msg="REG2 readback", scope="reg_walk", msg_id="ID_REG2",
        )
        check_value(
            0x42, 0x43, alert_level=AlertLevel.WARNING,
            msg="REG3 readback", scope="other", msg_id="ID_REG3",
        )

    def tearDown(self) -> None:
        reset_test_summary()

    # ---- construction ---------------------------------------------------- #

    def test_construct_with_default_fields(self):
        from hwval.docs import FieldSpec, SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
        )
        self.assertEqual(
            [f.name for f in d.fields],
            ["test_id", "msg", "scope", "msg_id", "passed", "detail"],
        )
        # Each default field appears in BOTH reports.
        for f in d.fields:
            self.assertEqual(
                f.reports, ("test_performed", "test_results")
            )
        # And the objects are real FieldSpec instances.
        self.assertTrue(all(isinstance(f, FieldSpec) for f in d.fields))

    def test_construct_with_custom_fields(self):
        from hwval.docs import FieldSpec, SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            fields=("msg", "scope"),
        )
        self.assertEqual([f.name for f in d.fields], ["msg", "scope"])
        self.assertTrue(all(isinstance(f, FieldSpec) for f in d.fields))

    def test_construct_accepts_field_spec_dicts(self):
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            fields=[
                "test_id",
                {"name": "msg", "reports": "test_results"},
                {"name": "operator", "reports": [
                    "test_performed", "test_results"]},
            ],
        )
        self.assertEqual([f.name for f in d.fields],
                         ["test_id", "msg", "operator"])
        self.assertEqual(d.fields[0].reports,
                         ("test_performed", "test_results"))
        self.assertEqual(d.fields[1].reports, ("test_results",))
        self.assertEqual(d.fields[2].reports,
                         ("test_performed", "test_results"))

    def test_construct_rejects_duplicate_field_names(self):
        from hwval.docs import SegDocument

        with self.assertRaises(ValueError):
            SegDocument(
                test_template=self.test_template,
                results_template=self.results_template,
                fields=("msg", "scope", "msg"),
            )

    def test_construct_rejects_non_identifier_field_name(self):
        from hwval.docs import SegDocument

        with self.assertRaises(ValueError):
            SegDocument(
                test_template=self.test_template,
                results_template=self.results_template,
                fields=("msg", "1bad-name"),
            )

    def test_unknown_field_defaults_to_empty_string(self):
        # Per the new contract: a YML-declared field that has no data
        # in a particular record shows up as "" in the rendered docx,
        # not as an error.
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            fields=("msg", "nope"),
        )
        # No exception; "nope" becomes "" in the projection.
        test_out = self.root / "out.docx"
        results_out = self.root / "out2.docx"
        d._generate(test_output=test_out, results_output=results_out)
        self.assertTrue(test_out.is_file())

    # ---- _generate basics ------------------------------------------------- #

    def test_generate_returns_two_paths(self):
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
        )
        test_out = self.root / "test_out.docx"
        results_out = self.root / "results_out.docx"
        t, r = d._generate(test_output=test_out, results_output=results_out)
        self.assertTrue(Path(t).is_file())
        self.assertTrue(Path(r).is_file())
        self.assertEqual(t, test_out)
        self.assertEqual(r, results_out)

    def test_generate_does_not_clear_accumulator(self):
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
        )
        before = current_summary()
        d._generate(
            test_output=self.root / "t.docx",
            results_output=self.root / "r.docx",
        )
        after = current_summary()
        self.assertEqual(before.total, after.total)
        self.assertEqual(before.failed_count, after.failed_count)

    def test_generate_renders_summary_into_template(self):
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
        )
        test_out = self.root / "test.docx"
        results_out = self.root / "results.docx"
        d._generate(test_output=test_out, results_output=results_out)

        lines = _read_paragraphs(test_out)
        self.assertEqual(lines[0], "Performed: 4")

        rlines = _read_paragraphs(results_out)
        self.assertEqual(rlines[0], "Total 4, 2 failed")

    def test_generate_uses_provided_summary(self):
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
        )
        custom = TestSummary(
            passed=[
                CheckRecord(scope="x", msg_id="i", msg="custom-pass",
                            passed=True, detail="d")
            ],
            failed=[],
        )
        results_out = self.root / "results_custom.docx"
        d._generate(
            test_output=self.root / "test_custom.docx",
            results_output=results_out,
            summary=custom,
        )
        rlines = _read_paragraphs(results_out)
        self.assertEqual(rlines[0], "Total 1, 0 failed")

    # ---- filtering ------------------------------------------------------- #

    def test_filter_limits_records(self):
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            filter=lambda r: r.scope == "reg_walk",
        )
        test_out = self.root / "test_filter.docx"
        results_out = self.root / "results_filter.docx"
        d._generate(test_output=test_out, results_output=results_out)

        # Only the 3 "reg_walk" records should remain (REG3 excluded).
        lines = _read_paragraphs(test_out)
        self.assertEqual(lines[0], "Performed: 3")
        rlines = _read_paragraphs(results_out)
        # Only REG1 fails within reg_walk scope.
        self.assertEqual(rlines[0], "Total 3, 1 failed")
        self.assertEqual(rlines[1:], ["REG1 readback#"])

    def test_include_passed_false(self):
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            include_passed=False,
        )
        test_out = self.root / "test.docx"
        results_out = self.root / "results.docx"
        d._generate(test_output=test_out, results_output=results_out)

        lines = _read_paragraphs(test_out)
        self.assertEqual(lines[0], "Performed: 2")
        # docxtpl's {%p for %} emits one paragraph per iteration.
        rlines = _read_paragraphs(results_out)
        self.assertEqual(rlines[0], "Total 2, 2 failed")
        self.assertEqual(rlines[1:], ["REG1 readback#", "REG3 readback#"])

    def test_include_failed_false(self):
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            include_failed=False,
        )
        results_out = self.root / "results.docx"
        d._generate(
            test_output=self.root / "test.docx",
            results_output=results_out,
        )
        rlines = _read_paragraphs(results_out)
        self.assertEqual(rlines[0], "Total 2, 0 failed")
        # Empty list -> no iteration paragraphs emitted.
        self.assertNotIn("REG1 readback#", rlines)
        self.assertNotIn("REG3 readback#", rlines)

    # ---- fields + extra_context ---------------------------------------- #

    def test_fields_limit_visible_record_keys(self):
        from hwval.docs import SegDocument
        from docx import Document

        # Template only references rec.msg and rec.scope.
        tpl = self.root / "fields.docx"
        _make_template(
            tpl,
            [
                "{%p for rec in records %}",
                "{{ rec.msg }}|{{ rec.scope }}",
                "{%p endfor %}",
            ],
        )
        rs = self.root / "fields_results.docx"
        d = SegDocument(
            test_template=tpl,
            results_template=tpl,
            fields=("msg", "scope"),
        )
        d._generate(test_output=rs, results_output=rs)

        doc = Document(str(rs))
        text = " ".join(p.text for p in doc.paragraphs)
        self.assertIn("REG0 readback|reg_walk", text)
        # 'msg_id' and 'detail' are excluded by `fields`.
        self.assertNotIn("ID_REG0", text)

    def test_extra_context_merges_into_render(self):
        from hwval.docs import SegDocument

        tpl = self.root / "ctx.docx"
        _make_template(tpl, ["Project: {{ project }}"])
        out = self.root / "ctx_out.docx"
        d = SegDocument(
            test_template=tpl,
            results_template=tpl,
            extra_context={"project": "Acme DUT v3", "operator": "alice"},
        )
        d._generate(test_output=out, results_output=out)
        self.assertEqual(_read_paragraphs(out)[0], "Project: Acme DUT v3")

    def test_generated_at_is_iso_utc(self):
        from hwval.docs import SegDocument

        tpl = self.root / "ts.docx"
        _make_template(tpl, ["{{ generated_at }}"])
        out = self.root / "ts_out.docx"
        d = SegDocument(test_template=tpl, results_template=tpl)
        d._generate(test_output=out, results_output=out)
        ts = _read_paragraphs(out)[0]
        # ISO 8601 UTC like 2026-09-18T09:26:00+00:00
        self.assertRegex(ts, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+\d{2}:\d{2}$")

    # ---- per-report fields + extras + missing-field default ----------- #

    def test_extras_appear_in_render_when_field_declared(self):
        from hwval.docs import SegDocument

        tpl = self.root / "extras.docx"
        _make_template(
            tpl,
            [
                "{%p for rec in records %}",
                "{{ rec.test_id }}|{{ rec.operator }}|{{ rec.msg }}",
                "{%p endfor %}",
            ],
        )
        out = self.root / "extras_out.docx"
        d = SegDocument(
            test_template=tpl,
            results_template=tpl,
            fields=("test_id", "operator", "msg"),
        )
        d._generate(test_output=out, results_output=out)
        from docx import Document
        text = " ".join(p.text for p in Document(str(out)).paragraphs)
        # setUp pre-populates 4 records, none of which pass `operator`,
        # so all rows must show "" for it.
        self.assertIn("TID_0001||REG0 readback", text)
        self.assertIn("TID_0004||REG3 readback", text)

    def test_extras_passed_in_check_value_show_up(self):
        from hwval.docs import SegDocument

        tpl = self.root / "with_extras.docx"
        _make_template(
            tpl,
            [
                "{%p for rec in records %}",
                "{{ rec.test_id }}|{{ rec.operator }}",
                "{%p endfor %}",
            ],
        )
        out = self.root / "with_extras_out.docx"
        d = SegDocument(
            test_template=tpl,
            results_template=tpl,
            fields=("test_id", "operator"),
        )
        # Add an extra record with `operator` supplied.
        check_value(
            0xAB, 0xAB, alert_level=AlertLevel.WARNING,
            msg="REG_EXTRA", scope="reg_walk", msg_id="ID_REG_EXTRA",
            operator="alice",
        )
        d._generate(test_output=out, results_output=out)
        from docx import Document
        text = " ".join(p.text for p in Document(str(out)).paragraphs)
        # The new record has operator=alice; the others are empty.
        self.assertIn("TID_0005|alice", text)
        # The old ones still get "" (per the contract).
        self.assertIn("TID_0001|", text)
        reset_test_summary()

    def test_missing_field_defaults_to_empty_string(self):
        # The user spec: a YML-declared field that is not passed to
        # check_value must show up as "" in the report, not raise.
        from hwval.docs import _record_to_dict

        check_value(1, 1, alert_level=AlertLevel.WARNING, msg="x")
        s = current_summary()
        d = _record_to_dict(s.passed[0], ["test_id", "operator", "notes"])
        self.assertEqual(d["test_id"], "TID_0001")
        self.assertEqual(d["operator"], "")
        self.assertEqual(d["notes"], "")

    def test_extras_override_builtin_when_names_collide(self):
        # An extra named exactly like a built-in field wins via the
        # projection (extras are checked first), letting the user
        # override `scope`/`msg` if they really want to. (The named
        # kwargs on check_value still go to the built-ins, so the
        # only way to put a same-named value in extras is to build
        # the record directly — which is what this test does.)
        from hwval import CheckRecord
        from hwval.docs import _record_to_dict

        rec = CheckRecord(
            scope="builtin_scope",
            msg_id="ID_X",
            msg="builtin_msg",
            passed=True,
            detail="d",
            extras={"scope": "override_scope", "msg": "override_msg"},
        )
        d = _record_to_dict(rec, ["scope", "msg"])
        self.assertEqual(d["scope"], "override_scope")
        self.assertEqual(d["msg"], "override_msg")

    def test_per_report_fields_filter_each_template(self):
        from hwval.docs import SegDocument

        # Two distinct templates: test_performed shows only the first
        # two fields, test_results shows the last two. The `msg` field
        # is restricted to test_results.
        performed_tpl = self.root / "performed.docx"
        results_tpl = self.root / "results.docx"
        _make_template(
            performed_tpl,
            [
                "{%p for rec in records %}",
                "{{ rec.test_id }}|{{ rec.scope }}",
                "{%p endfor %}",
            ],
        )
        _make_template(
            results_tpl,
            [
                "{%p for rec in records %}",
                "{{ rec.msg }}|{{ rec.detail }}",
                "{%p endfor %}",
            ],
        )
        out_p = self.root / "performed_out.docx"
        out_r = self.root / "results_out.docx"
        d = SegDocument(
            test_template=performed_tpl,
            results_template=results_tpl,
            fields=[
                {"name": "test_id", "reports": [
                    "test_performed", "test_results"]},
                {"name": "scope", "reports": "test_performed"},
                {"name": "msg", "reports": "test_results"},
                {"name": "detail", "reports": "test_results"},
            ],
        )
        d._generate(test_output=out_p, results_output=out_r)

        from docx import Document
        performed_text = " ".join(
            p.text for p in Document(str(out_p)).paragraphs
        )
        results_text = " ".join(
            p.text for p in Document(str(out_r)).paragraphs
        )
        # test_performed sees test_id+scope
        self.assertIn("TID_0001|reg_walk", performed_text)
        self.assertNotIn("REG0 readback", performed_text)
        # test_results sees msg+detail
        self.assertIn("REG1 readback|", results_text)
        self.assertNotIn("reg_walk", results_text)

    def test_per_report_field_list_in_jinja_fields_placeholder(self):
        from hwval.docs import SegDocument

        tpl = self.root / "hdr.docx"
        _make_template(tpl, ["{{ fields|join(',') }}"])
        performed = self.root / "performed.docx"
        results = self.root / "results.docx"
        # Same template for both so we can assert the two outputs
        # carry different field lists.
        d = SegDocument(
            test_template=tpl,
            results_template=tpl,
            fields=[
                {"name": "test_id", "reports": [
                    "test_performed", "test_results"]},
                {"name": "scope", "reports": "test_performed"},
                {"name": "msg", "reports": "test_results"},
            ],
        )
        d._generate(test_output=performed, results_output=results)
        self.assertEqual(_read_paragraphs(performed)[0],
                         "test_id,scope")
        self.assertEqual(_read_paragraphs(results)[0],
                         "test_id,msg")

    def test_fields_for_report_property(self):
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            fields=[
                "test_id",
                {"name": "scope", "reports": "test_performed"},
                {"name": "msg", "reports": "test_results"},
                {"name": "operator"},  # all reports
            ],
        )
        # _fields_for_report is a private helper but worth pinning.
        performed = d._fields_for_report("test_performed")
        results_ = d._fields_for_report("test_results")
        self.assertEqual([f.name for f in performed],
                         ["test_id", "scope", "operator"])
        self.assertEqual([f.name for f in results_],
                         ["test_id", "msg", "operator"])

    def test_value_and_expected_render_in_report(self):
        # `value` and `expected` are now part of CheckRecord, so
        # a YML-declared field can pull them straight into a row.
        from hwval.docs import SegDocument

        tpl = self.root / "val.docx"
        _make_template(
            tpl,
            [
                "{%p for rec in records %}",
                "{{ rec.test_id }}|{{ rec.value }}|{{ rec.expected }}",
                "{%p endfor %}",
            ],
        )
        out = self.root / "val_out.docx"
        d = SegDocument(
            test_template=tpl,
            results_template=tpl,
            fields=("test_id", "value", "expected"),
        )
        d._generate(test_output=out, results_output=out)
        from docx import Document
        text = " ".join(p.text for p in Document(str(out)).paragraphs)
        # setUp pre-populates with (1, 1) (pass), (2, 3) (fail),
        # (255, 255) (pass), (66, 67) (fail) — see test_docs.py
        # setUp. So value/expected are real numbers in each row.
        self.assertIn("TID_0001|1|1", text)
        self.assertIn("TID_0002|2|3", text)
        self.assertIn("TID_0003|255|255", text)
        self.assertIn("TID_0004|66|67", text)

    def test_report_prints_values_in_the_check_radix(self):
        # A check made with radix=HEX must show 0x.. in the report,
        # exactly like in the log line.
        from hwval.docs import SegDocument

        tpl = self.root / "radix.docx"
        _make_template(
            tpl,
            [
                "{%p for rec in records %}",
                "{{ rec.value }}|{{ rec.expected }}",
                "{%p endfor %}",
            ],
        )
        out = self.root / "radix_out.docx"

        reset_test_summary()
        check_value(
            0xDEAD, 0xDEAD, alert_level=AlertLevel.WARNING,
            msg="hex", radix=Radix.HEX,
        )
        check_value(
            42, 42, alert_level=AlertLevel.WARNING, msg="dec",
        )
        d = SegDocument(
            test_template=tpl,
            results_template=tpl,
            fields=("value", "expected"),
        )
        d._generate(test_output=out, results_output=out)
        from docx import Document
        text = " ".join(p.text for p in Document(str(out)).paragraphs)
        self.assertIn("0xDEAD|0xDEAD", text)
        self.assertIn("42|42", text)

    def test_report_keeps_the_raw_value_on_the_record(self):
        # The radix is a *display* concern: rec.value stays a number.
        from hwval.docs import SegDocument

        tpl = self.root / "raw.docx"
        _make_template(
            tpl,
            [
                "{%p for rec in records %}",
                "{{ rec.value }}",
                "{%p endfor %}",
            ],
        )
        out = self.root / "raw_out.docx"
        reset_test_summary()
        check_value(
            0xDEAD, 0xDEAD, alert_level=AlertLevel.WARNING,
            msg="hex", radix=Radix.HEX,
        )
        d = SegDocument(
            test_template=tpl,
            results_template=tpl,
            fields=("value",),
        )
        d._generate(test_output=out, results_output=out)
        from docx import Document
        text = " ".join(p.text for p in Document(str(out)).paragraphs)
        self.assertIn("0xDEAD", text)
        # … while the record itself keeps the int.
        self.assertEqual(current_summary().passed[0].value, 0xDEAD)

    # ---- error paths ----------------------------------------------------- #

    def test_missing_template_raises(self):
        from hwval.docs import SegDocument

        missing = self.root / "nope.docx"
        d = SegDocument(
            test_template=missing,
            results_template=missing,
        )
        with self.assertRaises(FileNotFoundError):
            d._generate(
                test_output=self.root / "out.docx",
                results_output=self.root / "out2.docx",
            )

    def test_missing_docxtpl_raises_clear_error(self):
        # Simulate missing extra by hiding docxtpl from sys.modules.
        import builtins
        import sys

        from hwval.docs import SegDocument

        hidden = sys.modules.copy()
        for name in list(sys.modules):
            if name == "docxtpl" or name.startswith("docx"):
                sys.modules.pop(name, None)
        # Block the import statement.
        original_import = builtins.__import__

        def _block(name, *a, **kw):
            if name == "docxtpl" or name.startswith("docxtpl"):
                raise ImportError("blocked for test")
            return original_import(name, *a, **kw)

        builtins.__import__ = _block
        try:
            with self.assertRaises(ImportError):
                SegDocument(
                    test_template=self.test_template,
                    results_template=self.results_template,
                )
        finally:
            builtins.__import__ = original_import
            sys.modules.update(hidden)

    # ---- test_id_function + YML config -------------------------------- #

    def test_test_id_function_callable_installs_globally(self):
        from hwval import get_test_id_function
        from hwval.docs import SegDocument

        def my_fn(record, seq):
            return f"MY_{seq:03d}"

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            test_id_function=my_fn,
        )
        self.assertIs(d.test_id_function, my_fn)
        self.assertIs(get_test_id_function(), my_fn)
        # The function is re-applied to the existing records; each
        # record keeps its 1-indexed position in the accumulator.
        # setUp pre-populates 4 checks in the order
        # [REG0 pass, REG1 fail, REG2 pass, REG3 fail].
        s = current_summary()
        self.assertEqual(s.passed[0].test_id, "MY_001")  # REG0
        self.assertEqual(s.failed[0].test_id, "MY_002")  # REG1
        self.assertEqual(s.passed[1].test_id, "MY_003")  # REG2
        self.assertEqual(s.failed[1].test_id, "MY_004")  # REG3

    def test_test_id_function_string_path_is_resolved(self):
        import sys
        import types

        from hwval import get_test_id_function
        from hwval.docs import SegDocument

        mod = types.ModuleType("_hwval_test_tid_mod")
        mod.make_tid = lambda rec, seq: f"PATH_{seq:03d}"
        sys.modules["_hwval_test_tid_mod"] = mod
        try:
            d = SegDocument(
                test_template=self.test_template,
                results_template=self.results_template,
                test_id_function="_hwval_test_tid_mod:make_tid",
            )
            self.assertIs(d.test_id_function, mod.make_tid)
            self.assertIs(get_test_id_function(), mod.make_tid)
        finally:
            del sys.modules["_hwval_test_tid_mod"]

    def test_test_id_function_none_does_not_overwrite(self):
        from hwval import get_test_id_function, set_test_id_function
        from hwval.docs import SegDocument

        sentinel = lambda rec, seq: "SENTINEL"
        set_test_id_function(sentinel)

        SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            test_id_function=None,
        )
        # Existing function is preserved.
        self.assertIs(get_test_id_function(), sentinel)

    def test_test_id_function_rejects_invalid_type(self):
        from hwval.docs import SegDocument

        with self.assertRaises(TypeError):
            SegDocument(
                test_template=self.test_template,
                results_template=self.results_template,
                test_id_function=42,
            )

    def test_resolve_callable_rejects_malformed_string(self):
        from hwval.docs import _resolve_callable

        with self.assertRaises(ValueError):
            _resolve_callable("no_colon_in_string")

    def test_resolve_callable_rejects_unknown_attr(self):
        from hwval.docs import _resolve_callable

        with self.assertRaises(AttributeError):
            _resolve_callable("os:nope_no_such_attr")

    def test_resolve_callable_rejects_non_callable_attr(self):
        from hwval.docs import _resolve_callable

        # `os` has a `sep` attribute, but it's a str, not a callable.
        with self.assertRaises(TypeError):
            _resolve_callable("os:sep")

    def test_test_id_in_default_fields(self):
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
        )
        self.assertIn("test_id", [f.name for f in d.fields])

    def test_test_id_visible_in_rendered_template(self):
        from hwval.docs import SegDocument

        tpl = self.root / "tid.docx"
        _make_template(
            tpl,
            [
                "{%p for rec in records %}",
                "{{ rec.test_id }}|{{ rec.msg }}",
                "{%p endfor %}",
            ],
        )
        out = self.root / "tid_out.docx"
        d = SegDocument(
            test_template=tpl,
            results_template=tpl,
        )
        d._generate(test_output=out, results_output=out)
        from docx import Document
        text = " ".join(p.text for p in Document(str(out)).paragraphs)
        self.assertIn("TID_0001|REG0 readback", text)
        self.assertIn("TID_0004|REG3 readback", text)

    @unittest.skipUnless(HAS_YAML, "requires pyyaml (hwval[docs] extra)")
    def test_config_yml_loads_fields(self):
        from hwval.docs import FieldSpec, SegDocument

        cfg = self.root / "hwval.yml"
        cfg.write_text(
            "fields:\n"
            "  - test_id\n"
            "  - msg\n"
            "  - scope\n"
        )
        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            config=cfg,
        )
        self.assertEqual([f.name for f in d.fields],
                         ["test_id", "msg", "scope"])
        self.assertTrue(all(isinstance(f, FieldSpec) for f in d.fields))

    @unittest.skipUnless(HAS_YAML, "requires pyyaml (hwval[docs] extra)")
    def test_config_yml_loads_per_report_fields(self):
        from hwval.docs import SegDocument

        cfg = self.root / "hwval.yml"
        cfg.write_text(
            "fields:\n"
            "  - test_id\n"
            "  - name: msg\n"
            "    reports: test_results\n"
            "  - name: scope\n"
            "    reports:\n"
            "      - test_performed\n"
            "      - test_results\n"
        )
        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            config=cfg,
        )
        self.assertEqual([f.name for f in d.fields],
                         ["test_id", "msg", "scope"])
        self.assertEqual(d.fields[0].reports,
                         ("test_performed", "test_results"))
        self.assertEqual(d.fields[1].reports, ("test_results",))
        self.assertEqual(d.fields[2].reports,
                         ("test_performed", "test_results"))

    @unittest.skipUnless(HAS_YAML, "requires pyyaml (hwval[docs] extra)")
    def test_config_yml_loads_include_toggles(self):
        from hwval.docs import SegDocument

        cfg = self.root / "hwval.yml"
        cfg.write_text(
            "include_passed: false\n"
            "include_failed: true\n"
        )
        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            config=cfg,
        )
        self.assertFalse(d.include_passed)
        self.assertTrue(d.include_failed)

    @unittest.skipUnless(HAS_YAML, "requires pyyaml (hwval[docs] extra)")
    def test_config_yml_installs_test_id_function(self):
        import sys
        import types

        from hwval import get_test_id_function
        from hwval.docs import SegDocument

        mod = types.ModuleType("_hwval_test_yml_tid_mod")
        mod.yml_tid = lambda rec, seq: f"YML_{seq:03d}"
        sys.modules["_hwval_test_yml_tid_mod"] = mod
        try:
            cfg = self.root / "hwval.yml"
            cfg.write_text(
                "test_id_function: "
                "\"_hwval_test_yml_tid_mod:yml_tid\"\n"
            )
            d = SegDocument(
                test_template=self.test_template,
                results_template=self.results_template,
                config=cfg,
            )
            self.assertIs(get_test_id_function(), mod.yml_tid)
            # setUp pre-populates 4 records; YML re-stamps them all
            # with the new function. First record was passed, so
            # passed[0] carries the first id.
            s = current_summary()
            self.assertEqual(s.passed[0].test_id, "YML_001")
        finally:
            del sys.modules["_hwval_test_yml_tid_mod"]

    @unittest.skipUnless(HAS_YAML, "requires pyyaml (hwval[docs] extra)")
    def test_config_yml_explicit_kwargs_win(self):
        from hwval.docs import SegDocument

        cfg = self.root / "hwval.yml"
        cfg.write_text(
            "fields:\n"
            "  - msg\n"
            "  - scope\n"
        )
        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            fields=("test_id", "msg", "scope", "msg_id"),
            config=cfg,
        )
        # Explicit kwargs take precedence over the YAML.
        self.assertEqual(
            [f.name for f in d.fields],
            ["test_id", "msg", "scope", "msg_id"],
        )

    @unittest.skipUnless(HAS_YAML, "requires pyyaml (hwval[docs] extra)")
    def test_config_yml_rejects_duplicate_field_name(self):
        from hwval.docs import SegDocument

        cfg = self.root / "hwval.yml"
        cfg.write_text(
            "fields:\n"
            "  - msg\n"
            "  - msg\n"
        )
        with self.assertRaises(ValueError):
            SegDocument(
                test_template=self.test_template,
                results_template=self.results_template,
                config=cfg,
            )

    @unittest.skipUnless(HAS_YAML, "requires pyyaml (hwval[docs] extra)")
    def test_config_yml_rejects_non_identifier_field_name(self):
        from hwval.docs import SegDocument

        cfg = self.root / "hwval.yml"
        cfg.write_text(
            "fields:\n"
            "  - 1bad-name\n"
        )
        with self.assertRaises(ValueError):
            SegDocument(
                test_template=self.test_template,
                results_template=self.results_template,
                config=cfg,
            )

    @unittest.skipUnless(HAS_YAML, "requires pyyaml (hwval[docs] extra)")
    def test_config_yml_unknown_key_raises(self):
        from hwval.docs import SegDocument

        cfg = self.root / "hwval.yml"
        cfg.write_text("nope: 1\n")
        with self.assertRaises(ValueError):
            SegDocument(
                test_template=self.test_template,
                results_template=self.results_template,
                config=cfg,
            )

    @unittest.skipUnless(HAS_YAML, "requires pyyaml (hwval[docs] extra)")
    def test_config_yml_wrong_type_raises(self):
        from hwval.docs import SegDocument

        cfg = self.root / "hwval.yml"
        cfg.write_text("fields: not-a-list\n")
        with self.assertRaises(TypeError):
            SegDocument(
                test_template=self.test_template,
                results_template=self.results_template,
                config=cfg,
            )

    def test_config_yml_missing_file_raises(self):
        from hwval.docs import SegDocument

        with self.assertRaises(FileNotFoundError):
            SegDocument(
                test_template=self.test_template,
                results_template=self.results_template,
                config=self.root / "nope.yml",
            )

    # ---- FieldSpec unit tests ---------------------------------------- #

    def test_fieldspec_coerce_from_string(self):
        from hwval.docs import FieldSpec

        spec = FieldSpec.coerce("msg")
        self.assertEqual(spec.name, "msg")
        # Default = both reports.
        self.assertEqual(spec.reports,
                         ("test_performed", "test_results"))

    def test_fieldspec_coerce_from_dict(self):
        from hwval.docs import FieldSpec

        spec = FieldSpec.coerce({"name": "msg", "reports": "test_results"})
        self.assertEqual(spec.name, "msg")
        self.assertEqual(spec.reports, ("test_results",))

    def test_fieldspec_coerce_from_dict_with_list(self):
        from hwval.docs import FieldSpec

        spec = FieldSpec.coerce(
            {"name": "x", "reports": ["test_performed"]}
        )
        self.assertEqual(spec.reports, ("test_performed",))

    def test_fieldspec_coerce_passthrough(self):
        from hwval.docs import FieldSpec

        spec = FieldSpec(name="x")
        self.assertIs(FieldSpec.coerce(spec), spec)

    def test_fieldspec_coerce_rejects_unknown_type(self):
        from hwval.docs import FieldSpec

        with self.assertRaises(TypeError):
            FieldSpec.coerce(42)

    def test_fieldspec_coerce_dict_without_name_raises(self):
        from hwval.docs import FieldSpec

        with self.assertRaises(ValueError):
            FieldSpec.coerce({"reports": "test_results"})

    def test_fieldspec_all_alias_expands(self):
        from hwval.docs import FieldSpec

        spec = FieldSpec(name="x", reports=("all",))
        self.assertEqual(spec.reports,
                         ("test_performed", "test_results"))

    def test_fieldspec_invalid_report_name_raises(self):
        from hwval.docs import FieldSpec

        with self.assertRaises(ValueError):
            FieldSpec(name="x", reports=("nope",))

    def test_fieldspec_in_report(self):
        from hwval.docs import FieldSpec

        spec = FieldSpec(name="x", reports=("test_results",))
        self.assertFalse(spec.in_report("test_performed"))
        self.assertTrue(spec.in_report("test_results"))

    @unittest.skipUnless(HAS_YAML, "requires pyyaml (hwval[docs] extra)")
    def test_config_yml_missing_pyyaml_raises_clear_error(self):
        import builtins
        import sys

        from hwval.docs import SegDocument

        cfg = self.root / "hwval.yml"
        cfg.write_text("fields: [msg]\n")

        hidden = sys.modules.copy()
        for name in list(sys.modules):
            if name == "yaml":
                sys.modules.pop(name, None)
        original_import = builtins.__import__

        def _block(name, *a, **kw):
            if name == "yaml":
                raise ImportError("blocked for test")
            return original_import(name, *a, **kw)

        builtins.__import__ = _block
        try:
            with self.assertRaises(ImportError):
                SegDocument(
                    test_template=self.test_template,
                    results_template=self.results_template,
                    config=cfg,
                )
        finally:
            builtins.__import__ = original_import
            sys.modules.update(hidden)


if __name__ == "__main__":
    unittest.main()
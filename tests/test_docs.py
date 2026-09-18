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


from hwval import (  # noqa: E402  (after the optional guard)
    AlertLevel,
    CheckRecord,
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
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
        )
        self.assertEqual(
            d.fields,
            ["msg", "scope", "msg_id", "passed", "detail"],
        )

    def test_construct_with_custom_fields(self):
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            fields=("msg", "scope"),
        )
        self.assertEqual(d.fields, ["msg", "scope"])

    def test_construct_rejects_unknown_field(self):
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
            fields=("msg", "nope"),
        )
        with self.assertRaises(AttributeError):
            d._generate(
                test_output=self.root / "out.docx",
                results_output=self.root / "out2.docx",
            )

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


if __name__ == "__main__":
    unittest.main()
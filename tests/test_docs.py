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
        from hwval.docs import SegDocument

        d = SegDocument(
            test_template=self.test_template,
            results_template=self.results_template,
        )
        self.assertEqual(
            d.fields,
            ["test_id", "msg", "scope", "msg_id", "passed", "detail"],
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
        self.assertIn("test_id", d.fields)

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
        from hwval.docs import SegDocument

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
        self.assertEqual(d.fields, ["test_id", "msg", "scope"])

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
            d.fields, ["test_id", "msg", "scope", "msg_id"]
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
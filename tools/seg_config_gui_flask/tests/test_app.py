"""Tests for the Flask-based SegDocument YML Config Generator.

Exercises every route + validation rule. Uses the Flask test
client (no live server) so the whole module runs in a few ms.
"""

from __future__ import annotations

import io
import unittest
from pathlib import Path

# Make the app importable regardless of how pytest is invoked.
HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parent
import sys
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

try:
    from app import create_app
    HAS_FLASK = True
except ImportError:  # pragma: no cover - depends on optional dep
    HAS_FLASK = False

try:
    from docx import Document  # type: ignore[import-not-found]
    HAS_DOCX = True
except ImportError:  # pragma: no cover - depends on optional dep
    HAS_DOCX = False


@unittest.skipUnless(HAS_FLASK, "requires flask (dev dep)")
class FlaskGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_app()
        cls.client = cls.app.test_client()

    # ---- basic routing ------------------------------------------------ #

    def test_get_root_renders_form(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn("YML Config Generator", body)
        self.assertIn("field_name", body)
        self.assertIn("test_id", body)
        # Default fields are pre-populated:
        self.assertIn('value="test_id"', body)
        self.assertIn('value="operator"', body)

    def test_healthz(self):
        r = self.client.get("/healthz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"status": "ok"})

    def test_post_root_generates_yml(self):
        r = self.client.post("/", data={
            "field_name": ["test_id", "msg", "operator"],
            "field_reports": ["all", "test_results", "all"],
            "include_passed": "on",
            "include_failed": "on",
            "test_id_function": "my_pkg.helpers:make_id",
        })
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn("YML is valid", body)
        self.assertIn("ready to download", body)
        # YML panel contains the generated text:
        self.assertIn("- test_id", body)
        self.assertIn("- name: msg", body)
        self.assertIn("reports: test_results", body)
        self.assertIn("test_id_function: &#34;my_pkg.helpers:make_id&#34;",
                      body)
        # Python-kwargs panel exists:
        self.assertIn("SegDocument(", body)
        self.assertIn("&#34;test_id&#34;", body)

    def test_post_root_emits_python_kwargs(self):
        r = self.client.post("/", data={
            "field_name": ["test_id", "msg"],
            "field_reports": ["all", "test_results"],
            "include_passed": "on",
            "include_failed": "on",
            "test_id_function": "",
        })
        body = r.get_data(as_text=True)
        # Every field with reports != "all" is emitted as a dict.
        self.assertIn(
            '{&#34;name&#34;: &#34;msg&#34;, '
            '&#34;reports&#34;: &#34;test_results&#34;},',
            body,
        )
        # Every field with reports == "all" is emitted as a string.
        self.assertIn('&#34;test_id&#34;,', body)
        # Boolean toggles capitalised.
        self.assertIn("include_passed=True", body)
        self.assertIn("include_failed=True", body)
        # No test_id_function kwarg when the field is empty.
        self.assertNotIn("test_id_function=", body)

    def test_post_root_skips_blank_field_names(self):
        # Empty rows (someone clicked + Add Field and left the name
        # blank) are silently dropped, not flagged.
        r = self.client.post("/", data={
            "field_name": ["test_id", "", "msg"],
            "field_reports": ["all", "all", "test_results"],
            "include_passed": "on",
            "include_failed": "on",
        })
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn("YML is valid", body)

    # ---- validation errors ------------------------------------------- #

    def test_post_rejects_invalid_identifier(self):
        r = self.client.post("/", data={
            "field_name": ["1bad-name", "ok"],
            "field_reports": ["all", "all"],
            "include_passed": "on",
            "include_failed": "on",
        })
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn("Could not generate YML", body)
        self.assertIn("1bad-name", body)
        self.assertIn("not a valid Python identifier", body)

    def test_post_rejects_duplicate_field(self):
        r = self.client.post("/", data={
            "field_name": ["msg", "msg"],
            "field_reports": ["all", "test_results"],
            "include_passed": "on",
            "include_failed": "on",
        })
        body = r.get_data(as_text=True)
        self.assertIn("duplicate name", body)

    def test_post_rejects_bad_test_id_function(self):
        r = self.client.post("/", data={
            "field_name": ["msg"],
            "field_reports": ["all"],
            "include_passed": "on",
            "include_failed": "on",
            "test_id_function": "no_colon_here",
        })
        body = r.get_data(as_text=True)
        self.assertIn("test_id_function must be in", body)

    def test_post_rejects_empty_test_id_function_colon(self):
        r = self.client.post("/", data={
            "field_name": ["msg"],
            "field_reports": ["all"],
            "include_passed": "on",
            "include_failed": "on",
            "test_id_function": ":just_colon",
        })
        body = r.get_data(as_text=True)
        self.assertIn("test_id_function must be in", body)

    def test_post_accepts_no_fields(self):
        # Empty fields list: at least one field is required.
        r = self.client.post("/", data={
            "field_name": [],
            "field_reports": [],
            "include_passed": "on",
            "include_failed": "on",
        })
        body = r.get_data(as_text=True)
        self.assertIn("Add at least one field", body)

    def test_post_normalises_invalid_reports_value(self):
        # An attacker / stale form tampering a reports dropdown to
        # something other than the three known values is silently
        # coerced back to "all" before the YML is built.
        r = self.client.post("/", data={
            "field_name": ["msg"],
            "field_reports": ["bogus"],
            "include_passed": "on",
            "include_failed": "on",
        })
        body = r.get_data(as_text=True)
        self.assertIn("YML is valid", body)
        self.assertIn("- msg", body)

    def test_post_toggles_default_to_false(self):
        # Without the checkbox on, include_passed / include_failed
        # default to False in the YML.
        r = self.client.post("/", data={
            "field_name": ["msg"],
            "field_reports": ["all"],
            # no include_passed / include_failed
            "test_id_function": "",
        })
        body = r.get_data(as_text=True)
        self.assertIn("YML is valid", body)
        self.assertIn("include_passed: false", body)
        self.assertIn("include_failed: false", body)

    # ---- /download ---------------------------------------------------- #

    def test_download_returns_yaml_attachment(self):
        r = self.client.post("/download", data={
            "field_name": ["test_id", "msg"],
            "field_reports": ["all", "test_results"],
            "include_passed": "on",
            "include_failed": "on",
            "test_id_function": "",
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/yaml", r.headers["Content-Type"])
        self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertIn("hwval.yml", r.headers["Content-Disposition"])
        body = r.get_data(as_text=True)
        self.assertIn("fields:", body)
        self.assertIn("- test_id", body)
        self.assertIn("- name: msg", body)
        self.assertIn("reports: test_results", body)
        self.assertIn("include_passed: true", body)
        self.assertIn("include_failed: true", body)

    def test_download_rejects_invalid_input(self):
        r = self.client.post("/download", data={
            "field_name": ["1bad"],
            "field_reports": ["all"],
            "include_passed": "on",
            "include_failed": "on",
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("validation failed", r.get_data(as_text=True))

    def test_download_yml_loads_via_real_loader(self):
        # Defence in depth: the YML the form emits must round-trip
        # through hwval.docs.load_seg_config without error.
        from hwval.docs import load_seg_config

        r = self.client.post("/download", data={
            "field_name": ["test_id", "msg", "operator"],
            "field_reports": ["all", "test_results", "all"],
            "include_passed": "on",
            "include_failed": "on",
            "test_id_function": "pkg.mod:fn",
        })
        self.assertEqual(r.status_code, 200)
        yml = r.get_data(as_text=True)

        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            f.write(yml)
            path = f.name
        try:
            cfg = load_seg_config(path)
        finally:
            import os
            os.unlink(path)

        # Verify the loader produced the expected FieldSpec list.
        from hwval.docs import FieldSpec
        self.assertEqual(
            cfg["fields"],
            [
                FieldSpec(name="test_id"),
                FieldSpec(name="msg", reports=("test_results",)),
                FieldSpec(name="operator"),
            ],
        )
        self.assertTrue(cfg["include_passed"])
        self.assertTrue(cfg["include_failed"])
        self.assertEqual(cfg["test_id_function"], "pkg.mod:fn")

    # ---- extra_context ----------------------------------------------- #

    def test_get_shows_extra_context_rows(self):
        r = self.client.get("/")
        body = r.get_data(as_text=True)
        self.assertIn("ctx_key", body)
        self.assertIn("ctx_value", body)
        # The default rows are pre-populated.
        self.assertIn('value="project"', body)
        self.assertIn('value="operator"', body)

    def test_post_round_trips_extra_context(self):
        r = self.client.post("/", data={
            "field_name": ["msg"],
            "field_reports": ["all"],
            "include_passed": "on",
            "include_failed": "on",
            "ctx_key": ["project", "dut_serial"],
            "ctx_value": ["Acme DUT v3", "SN-42"],
        })
        body = r.get_data(as_text=True)
        self.assertIn("YML is valid", body)
        # The rows survive the round-trip.
        self.assertIn('value="project"', body)
        self.assertIn('value="Acme DUT v3"', body)
        self.assertIn('value="dut_serial"', body)
        self.assertIn('value="SN-42"', body)

    def test_post_emits_extra_context_in_python_kwargs(self):
        r = self.client.post("/", data={
            "field_name": ["msg"],
            "field_reports": ["all"],
            "include_passed": "on",
            "include_failed": "on",
            "ctx_key": ["project", "operator"],
            "ctx_value": ["Acme DUT v3", "alice"],
        })
        body = r.get_data(as_text=True)
        self.assertIn("extra_context={", body)
        self.assertIn("&#34;project&#34;: &#34;Acme DUT v3&#34;,", body)
        self.assertIn("&#34;operator&#34;: &#34;alice&#34;,", body)

    def test_post_coerces_scalar_context_values(self):
        r = self.client.post("/", data={
            "field_name": ["msg"],
            "field_reports": ["all"],
            "include_passed": "on",
            "include_failed": "on",
            "ctx_key": ["build", "ratio", "flag", "nothing", "label"],
            "ctx_value": ["42", "1.5", "true", "null", "hello"],
        })
        body = r.get_data(as_text=True)
        self.assertIn("&#34;build&#34;: 42,", body)
        self.assertIn("&#34;ratio&#34;: 1.5,", body)
        self.assertIn("&#34;flag&#34;: True,", body)
        self.assertIn("&#34;nothing&#34;: None,", body)
        self.assertIn("&#34;label&#34;: &#34;hello&#34;,", body)

    def test_post_rejects_invalid_context_key(self):
        r = self.client.post("/", data={
            "field_name": ["msg"],
            "field_reports": ["all"],
            "ctx_key": ["2bad-key"],
            "ctx_value": ["x"],
        })
        body = r.get_data(as_text=True)
        self.assertIn("Could not generate YML", body)
        self.assertIn("not a valid Python identifier", body)

    def test_post_rejects_python_keyword_context_key(self):
        r = self.client.post("/", data={
            "field_name": ["msg"],
            "field_reports": ["all"],
            "ctx_key": ["for"],
            "ctx_value": ["x"],
        })
        body = r.get_data(as_text=True)
        self.assertIn("not a valid Python identifier", body)

    def test_post_rejects_duplicate_context_key(self):
        r = self.client.post("/", data={
            "field_name": ["msg"],
            "field_reports": ["all"],
            "ctx_key": ["project", "project"],
            "ctx_value": ["a", "b"],
        })
        body = r.get_data(as_text=True)
        self.assertIn("duplicate key", body)

    def test_post_rejects_reserved_context_key(self):
        # "records" is provided by SegDocument itself; shadowing it
        # would break the generated template's row loop.
        r = self.client.post("/", data={
            "field_name": ["msg"],
            "field_reports": ["all"],
            "ctx_key": ["records"],
            "ctx_value": ["x"],
        })
        body = r.get_data(as_text=True)
        self.assertIn("reserved name", body)

    def test_post_skips_blank_context_key(self):
        # A row with no key is ignored (like a blank field name).
        # The row itself is preserved in the form so the user can
        # fill the key in, but it never reaches the config.
        r = self.client.post("/", data={
            "field_name": ["msg"],
            "field_reports": ["all"],
            "include_passed": "on",
            "include_failed": "on",
            "ctx_key": ["", "project"],
            "ctx_value": ["orphan", "Acme"],
        })
        body = r.get_data(as_text=True)
        self.assertIn("YML is valid", body)
        kwargs = body.split('<pre class="code">')[2].split("</pre>")[0]
        self.assertIn("&#34;project&#34;: &#34;Acme&#34;,", kwargs)
        self.assertNotIn("orphan", kwargs)

    def test_extra_context_is_not_written_to_the_yml(self):
        # load_seg_config only accepts fields / include_passed /
        # include_failed / test_id_function — extra_context would be
        # an unknown key and would break the loader.
        r = self.client.post("/", data={
            "field_name": ["msg"],
            "field_reports": ["all"],
            "include_passed": "on",
            "include_failed": "on",
            "ctx_key": ["project"],
            "ctx_value": ["Acme"],
        })
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        yml = body.split('<pre class="code">')[1].split("</pre>")[0]
        self.assertNotIn("project", yml)
        self.assertNotIn("extra_context", yml)

    # ---- /download-template/<report> --------------------------------- #

    def _download_template(self, report, **overrides):
        data = {
            "field_name": ["test_id", "msg", "operator"],
            "field_reports": ["all", "test_results", "all"],
            "include_passed": "on",
            "include_failed": "on",
            "ctx_key": ["project"],
            "ctx_value": ["Acme DUT v3"],
        }
        data.update(overrides)
        return self.client.post(f"/download-template/{report}", data=data)

    def test_download_template_returns_docx_attachment(self):
        r = self._download_template("test_results")
        self.assertEqual(r.status_code, 200)
        self.assertIn(
            "wordprocessingml.document", r.headers["Content-Type"]
        )
        self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertIn(
            "test_results.docx", r.headers["Content-Disposition"]
        )

    def test_download_template_rejects_unknown_report(self):
        r = self._download_template("nope")
        self.assertEqual(r.status_code, 404)
        self.assertIn("unknown report", r.get_data(as_text=True))

    def test_download_template_rejects_invalid_input(self):
        r = self._download_template(
            "test_results", field_name=["1bad"], field_reports=["all"]
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("validation failed", r.get_data(as_text=True))

    def test_download_template_rejects_invalid_context_key(self):
        r = self._download_template("test_results", ctx_key=["2bad"])
        self.assertEqual(r.status_code, 400)
        self.assertIn("validation failed", r.get_data(as_text=True))

    @unittest.skipUnless(HAS_DOCX, "requires python-docx")
    def test_downloaded_template_contains_user_fields(self):
        # The test_results template carries the fields scoped to that
        # report only.
        r = self._download_template("test_results")
        self.assertEqual(r.status_code, 200)
        doc = Document(io.BytesIO(r.get_data()))
        headers = [
            [c.text for c in row.cells] for row in doc.tables[0].rows
        ]
        self.assertEqual(headers[0], ["test_id", "msg", "operator"])
        # The data row holds one placeholder per field.
        self.assertEqual(
            headers[2],
            [
                "{{ rec.test_id }}",
                "{{ rec.msg }}",
                "{{ rec.operator }}",
            ],
        )

    @unittest.skipUnless(HAS_DOCX, "requires python-docx")
    def test_downloaded_template_scopes_fields_per_report(self):
        # "msg" is scoped to test_results, so the test_performed
        # template must not carry it.
        r = self._download_template("test_performed")
        self.assertEqual(r.status_code, 200)
        doc = Document(io.BytesIO(r.get_data()))
        headers = [c.text for c in doc.tables[0].rows[0].cells]
        self.assertEqual(headers, ["test_id", "operator"])
        self.assertNotIn("msg", headers)

    @unittest.skipUnless(HAS_DOCX, "requires python-docx")
    def test_downloaded_template_contains_extra_context(self):
        r = self._download_template(
            "test_results",
            ctx_key=["project", "dut_serial"],
            ctx_value=["Acme DUT v3", "SN-42"],
        )
        self.assertEqual(r.status_code, 200)
        doc = Document(io.BytesIO(r.get_data()))
        text = "\n".join(p.text for p in doc.paragraphs)
        self.assertIn("{{ project }}", text)
        self.assertIn("{{ dut_serial }}", text)
        # ... and the label is derived from the key.
        self.assertIn("Project:", text)
        self.assertIn("Dut Serial:", text)

    @unittest.skipUnless(HAS_DOCX, "requires python-docx")
    def test_downloaded_template_renders_through_docxtpl(self):
        # End-to-end: the generated template must be a valid docxtpl
        # template that renders one row per record.
        from docxtpl import DocxTemplate

        r = self._download_template("test_results")
        docx_bytes = r.get_data()
        tpl = DocxTemplate(io.BytesIO(docx_bytes))
        tpl.render({
            "project": "Acme DUT v3",
            "generated_at": "2026-10-26T15:00:00+00:00",
            "fields": ["test_id", "msg", "operator"],
            "summary": {"total": 2, "passed_count": 1, "failed_count": 1},
            "failed": [
                {"test_id": "T1", "msg": "boom", "operator": "alice"},
                {"test_id": "T2", "msg": "bang", "operator": "alice"},
            ],
            "passed": [
                {"test_id": "T3", "msg": "ok", "operator": "alice"},
            ],
        })
        out = io.BytesIO()
        tpl.save(out)

        doc = Document(out)
        rendered = [
            [c.text for c in row.cells] for row in doc.tables[0].rows
        ]
        # Header + one row per failed record; the {%tr %} tag rows
        # are removed by docxtpl.
        self.assertEqual(len(rendered), 3)
        self.assertEqual(rendered[0], ["test_id", "msg", "operator"])
        self.assertEqual(rendered[1][0], "T1")
        self.assertEqual(rendered[2][0], "T2")

    @unittest.skipUnless(HAS_DOCX, "requires python-docx")
    def test_downloaded_template_without_fields_for_report(self):
        # Every field is scoped to test_results -> the test_performed
        # template has nothing to tabulate and must not crash.
        r = self._download_template(
            "test_performed",
            field_name=["msg"],
            field_reports=["test_results"],
        )
        self.assertEqual(r.status_code, 200)
        doc = Document(io.BytesIO(r.get_data()))
        self.assertEqual(len(doc.tables), 0)
        self.assertIn(
            "No fields are configured",
            "\n".join(p.text for p in doc.paragraphs),
        )


if __name__ == "__main__":
    unittest.main()

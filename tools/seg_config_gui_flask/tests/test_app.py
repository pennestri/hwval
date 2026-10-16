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


if __name__ == "__main__":
    unittest.main()

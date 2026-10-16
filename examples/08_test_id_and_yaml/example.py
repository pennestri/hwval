"""Demo: ``test_id`` field + YML-driven ``SegDocument`` config +
per-report field scoping + ``**extras`` on check_value.

Run with::

    uv run python examples/08_test_id_and_yaml/example.py

This script:

  1. Loads the SegDocument config from ``hwval.yml`` next to it.
     The YML scopes each field to either the test_performed report
     or the test_results report (or both).
  2. Runs a few WARNING checks via ``check_value``. Two of them pass
     ``operator="..."`` and ``seq_id="..."`` as ``**extras``; the
     YML declares ``operator`` (both reports) but not ``seq_id``,
     so ``seq_id`` is stored but never rendered.
  3. The user-supplied ``make_test_id`` from ``test_id_helpers.py``
     fills each ``CheckRecord.test_id`` (and the same id ends up in
     the log lines).
  4. Renders the two .docx outputs and prints the rendered text so
     the per-report field split and the missing-field defaulting to
     ``""`` are visible end-to-end.

Requires the optional ``hwval[docs]`` extra (docxtpl, python-docx,
jinja2, pyyaml).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Make the ``examples`` package importable so the YML config can
# resolve ``examples.08_test_id_and_yaml.test_id_helpers:make_test_id``.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from docx import Document
except ImportError:
    sys.stderr.write(
        "examples/08_test_id_and_yaml/example.py requires the "
        "hwval[docs] extra.\n"
        "Install it with:  uv add hwval[docs]   "
        "(or: pip install hwval[docs])\n"
    )
    raise

from hwval import (
    AlertLevel,
    SegDocument,
    check_value,
    reset_test_summary,
)


HERE = Path(__file__).resolve().parent
CONFIG = HERE / "hwval.yml"


def _build_template(path: Path, paragraphs: list[str]) -> None:
    """Each entry in ``paragraphs`` becomes one paragraph in the docx."""
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    doc.save(path)


def _build_templates(tmp: Path) -> tuple[Path, Path]:
    test_tpl = tmp / "test_performed.docx"
    results_tpl = tmp / "test_results.docx"

    # The fields placeholder echoes the YML-filtered list of fields
    # for this report, so each template can show its own column list.
    _build_template(
        test_tpl,
        [
            "Acme DUT v3 — Test Performed",
            "Project: {{ project }}    Operator: {{ operator }}",
            "Generated: {{ generated_at }}",
            "Fields: {{ fields|join(', ') }}",
            "",
            "Tests performed: {{ summary.total }}",
            "{%p for rec in records %}",
            "  - [{{ rec.test_id }}] "
            "[{{ rec.msg_id }}] op={{ rec.operator }}",
            "{%p endfor %}",
        ],
    )
    _build_template(
        results_tpl,
        [
            "Acme DUT v3 — Test Results",
            "Project: {{ project }}    Operator: {{ operator }}",
            "Fields: {{ fields|join(', ') }}",
            "",
            "Total: {{ summary.total }}    "
            "Passed: {{ summary.passed_count }}    "
            "Failed: {{ summary.failed_count }}",
            "{%p for rec in failed %}",
            "  - [{{ rec.test_id }}] op={{ rec.operator }}: {{ rec.msg }}",
            "    detail: {{ rec.detail }}",
            "{%p endfor %}",
        ],
    )
    return test_tpl, results_tpl


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        test_tpl, results_tpl = _build_templates(Path(tmp))

        # --- 2. Run a few WARNING checks -------------------------------
        # Some records pass `operator=` (declared in YML) and one
        # record also passes `seq_id=` (NOT declared in YML → stored
        # on the record but never rendered in the report).
        reset_test_summary()
        check_value(0xDEAD, 0xDEAD, alert_level=AlertLevel.WARNING,
                    msg="REG0 OK", scope="reg_walk", msg_id="ID_REG0",
                    operator="alice")
        check_value(0xBEEF, 0xCAFE, alert_level=AlertLevel.WARNING,
                    msg="REG1 drift", scope="reg_walk", msg_id="ID_REG1",
                    operator="alice", seq_id="A1")
        check_value(0x1234, 0x1234, alert_level=AlertLevel.WARNING,
                    msg="REG2 OK", scope="reg_walk", msg_id="ID_REG2",
                    operator="bob")
        # No `operator` here — it shows up as "" in the rendered
        # report (per the "missing field defaults to empty string"
        # contract).
        check_value(0x9999, 0x0001, alert_level=AlertLevel.WARNING,
                    msg="REG3 mismatch", scope="reg_walk", msg_id="ID_REG3")

        # --- 3. Build the SegDocument straight from the YAML ----------
        # No fields=, no test_id_function=, no toggles in Python. The
        # YAML is the single source of truth for the report layout.
        doc = SegDocument(
            test_template=test_tpl,
            results_template=results_tpl,
            config=CONFIG,
            extra_context={"project": "Acme DUT v3", "operator": "alice"},
        )

        # --- 4. Render the two .docx files ----------------------------
        out_dir = HERE / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(test_tpl, out_dir / "test_performed.docx")
        shutil.copy(results_tpl, out_dir / "test_results.docx")

        test_out, results_out = doc._generate(
            test_output=out_dir / "test_performed_OUT.docx",
            results_output=out_dir / "test_results_OUT.docx",
        )

        # --- 5. Print the rendered text --------------------------------
        print(f"rendered: {test_out}")
        print(f"rendered: {results_out}")
        for label, path in [("test performed", test_out),
                            ("test results", results_out)]:
            print(f"\n--- {label} ({path.name}) ---")
            rendered = Document(str(path))
            for p in rendered.paragraphs:
                if p.text.strip():
                    print(p.text)


if __name__ == "__main__":
    main()

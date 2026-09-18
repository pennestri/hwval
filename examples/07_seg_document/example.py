"""Demo: ``SegDocument._generate`` — render two .docx reports.

Requires the optional ``hwval[docs]`` extra:

    uv add hwval[docs]
    # or
    pip install hwval[docs]

This script:

  1. Creates two minimal Jinja2+docx templates in a temp directory
     (one for "test performed", one for "test results").
  2. Runs a few WARNING checks via ``check_value`` so there's data
     to report.
  3. Calls ``SegDocument._generate(...)`` to render the two .docx files.
  4. Prints the rendered output paths.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from docx import Document  # type: ignore[import-not-found]  # from hwval[docs]

from hwval import (
    AlertLevel,
    SegDocument,
    check_value,
    reset_test_summary,
)


def _build_template(path: Path, paragraphs: list[str]) -> None:
    """Write a minimal .docx template. Each list entry = one paragraph.

    docxtpl's ``{%p ... %}`` tags must sit on a paragraph of their own.
    """
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    doc.save(path)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # --- 1. Templates -------------------------------------------------
        test_tpl = root / "test_performed.docx"
        results_tpl = root / "test_results.docx"

        _build_template(
            test_tpl,
            [
                "Acme DUT v3 — Test Performed",
                "Operator: {{ operator }}",
                "Generated: {{ generated_at }}",
                "",
                "Tests performed: {{ summary.total }}",
                "{%p for rec in records %}",
                "  - [{{ rec.scope }}] {{ rec.msg_id }}: {{ rec.msg }}",
                "{%p endfor %}",
            ],
        )
        _build_template(
            results_tpl,
            [
                "Acme DUT v3 — Test Results",
                "Operator: {{ operator }}",
                "",
                "Total: {{ summary.total }}    "
                "Passed: {{ summary.passed_count }}    "
                "Failed: {{ summary.failed_count }}",
                "{%p for rec in failed %}",
                "  - [{{ rec.scope }}] {{ rec.msg_id }}: {{ rec.msg }}",
                "    {{ rec.detail }}",
                "{%p endfor %}",
            ],
        )

        # --- 2. Run some checks ------------------------------------------
        reset_test_summary()

        check_value(0xDEAD, 0xDEAD, alert_level=AlertLevel.WARNING,
                    msg="REG0 OK", scope="reg_walk", msg_id="ID_REG0")
        check_value(0xBEEF, 0xCAFE, alert_level=AlertLevel.WARNING,
                    msg="REG1 drift", scope="reg_walk", msg_id="ID_REG1")
        check_value(0x1234, 0x1234, alert_level=AlertLevel.WARNING,
                    msg="REG2 OK", scope="reg_walk", msg_id="ID_REG2")
        check_value(0x9999, 0x0001, alert_level=AlertLevel.WARNING,
                    msg="REG3 mismatch", scope="reg_walk", msg_id="ID_REG3")

        # --- 3. Render the two .docx files -------------------------------
        # Copy the templates into an output folder the user can keep.
        out_dir = Path("examples/07_seg_document/out").resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(test_tpl, out_dir / "test_performed.docx")
        shutil.copy(results_tpl, out_dir / "test_results.docx")

        doc = SegDocument(
            test_template=out_dir / "test_performed.docx",
            results_template=out_dir / "test_results.docx",
            fields=("msg_id", "msg", "scope", "detail"),
            filter=lambda r: r.scope == "reg_walk",
            extra_context={"operator": "alice"},
        )

        # `_generate` overwrites the template-in-place (we keep them
        # alongside the rendered output for comparison).
        test_out, results_out = doc._generate(
            test_output=out_dir / "test_performed_OUT.docx",
            results_output=out_dir / "test_results_OUT.docx",
        )

        # --- 4. Show the results -----------------------------------------
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
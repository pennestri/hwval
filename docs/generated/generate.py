"""Generate project-level docx reports for `hwval`.

This script dogfoods `SegDocument` — it runs a battery of
`check_value` / `check_value_in_range` calls (one per public feature,
all at `WARNING` so they don't raise) and renders two `.docx` files
describing the project's own test surface.

Run with:

    uv run python docs/generated/generate.py

Outputs are written next to this script:

    hwval_test_performed.docx   what was tested
    hwval_test_results.docx    what the results were
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

# `docxtpl` + `python-docx` come from the [docs] extra.
try:
    from docx import Document
except ImportError:
    sys.stderr.write(
        "docs/generated/generate.py requires the hwval[docs] extra.\n"
        "Install it with:  uv add hwval[docs]   (or: pip install hwval[docs])\n"
    )
    raise

from hwval import (
    AlertLevel,
    MatchStrictness,
    Radix,
    SegDocument,
    check_value,
    check_value_in_range,
    reset_test_summary,
)


HERE = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- #
# Test data                                                                   #
# --------------------------------------------------------------------------- #


def _run_self_checks() -> None:
    """Exercise each public surface so there's data to report on."""
    reset_test_summary()

    # check_value: pass, fail, sequence
    check_value(42, 42, alert_level=AlertLevel.WARNING,
                msg="check_value: int pass", scope="checks",
                msg_id="ID_CHECK_INT")
    check_value(1, 2, alert_level=AlertLevel.WARNING,
                msg="check_value: int fail (expected)", scope="checks",
                msg_id="ID_CHECK_INT")
    check_value([0xDE, 0xAD], [0xDE, 0xAD], alert_level=AlertLevel.WARNING,
                msg="check_value: vector pass", scope="checks",
                msg_id="ID_CHECK_VEC",
                radix=Radix.HEX)

    # check_value_in_range: pass, fail, boundary
    check_value_in_range(50, 10, 100, alert_level=AlertLevel.WARNING,
                          msg="range: inside", scope="checks",
                          msg_id="ID_RANGE_IN")
    check_value_in_range(150, 10, 100, alert_level=AlertLevel.WARNING,
                          msg="range: outside (expected)", scope="checks",
                          msg_id="ID_RANGE_OUT")
    check_value_in_range(10, 10, 100, alert_level=AlertLevel.WARNING,
                          msg="range: lower boundary", scope="checks",
                          msg_id="ID_RANGE_BOUND")

    # radix
    check_value(0xCAFE, 0xCAFE, alert_level=AlertLevel.WARNING,
                msg="radix: HEX", scope="formatting",
                msg_id="ID_RADIX_HEX", radix=Radix.HEX)
    check_value(0b1010, 0b1010, alert_level=AlertLevel.WARNING,
                msg="radix: BIN", scope="formatting",
                msg_id="ID_RADIX_BIN", radix=Radix.BIN)

    # match strictness (positional)
    check_value(7, 7, MatchStrictness.MATCH_EXACT, alert_level=AlertLevel.WARNING,
                msg="match: MATCH_EXACT", scope="formatting",
                msg_id="ID_MATCH")

    # scopes and msg_ids are real-world tags
    check_value(0, 0, alert_level=AlertLevel.WARNING,
                msg="reg_walk: REG0 OK", scope="reg_walk",
                msg_id="ID_REG0")
    check_value(1, 2, alert_level=AlertLevel.WARNING,
                msg="reg_walk: REG1 drift", scope="reg_walk",
                msg_id="ID_REG1")

    # logging + summary integration
    check_value(0xFF, 0xFF, alert_level=AlertLevel.WARNING,
                msg="adc: sample in band", scope="adc",
                msg_id="ID_ADC_OK")


# --------------------------------------------------------------------------- #
# Templates                                                                   #
# --------------------------------------------------------------------------- #


def _build_template(path: Path, paragraphs: list[str]) -> None:
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    doc.save(path)


def _build_templates(tmp: Path) -> tuple[Path, Path]:
    test_tpl = tmp / "test_performed.docx"
    results_tpl = tmp / "test_results.docx"

    _build_template(
        test_tpl,
        [
            "hwval — Test Performed",
            "Project: {{ project }}",
            "Operator: {{ operator }}",
            "Generated: {{ generated_at }}",
            "",
            "Tests performed: {{ summary.total }}",
            "Scopes covered: {{ scopes }}",
            "{%p for rec in records %}",
            "  - [{{ rec.scope }}] {{ rec.msg_id }}: {{ rec.msg }}",
            "{%p endfor %}",
        ],
    )
    _build_template(
        results_tpl,
        [
            "hwval — Test Results",
            "Project: {{ project }}",
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
    return test_tpl, results_tpl


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        test_tpl, results_tpl = _build_templates(Path(tmp))

        _run_self_checks()

        doc = SegDocument(
            test_template=test_tpl,
            results_template=results_tpl,
            fields=("msg_id", "msg", "scope", "detail"),
            extra_context={
                "project": "hwval",
                "operator": "release-bot",
                "scopes": "checks, formatting, reg_walk, adc",
            },
        )

        test_out = HERE / "hwval_test_performed.docx"
        results_out = HERE / "hwval_test_results.docx"
        doc._generate(test_output=test_out, results_output=results_out)

        print(f"rendered: {test_out}")
        print(f"rendered: {results_out}")


if __name__ == "__main__":
    main()
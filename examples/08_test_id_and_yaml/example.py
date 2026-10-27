"""Demo: ``test_id`` field + YML-driven ``SegDocument`` config +
per-report field scoping + ``**extras`` on check_value.

Run with::

    uv run python examples/08_test_id_and_yaml/example.py

This script:

  1. Loads the SegDocument config from ``hwval.yml`` next to it.
     The YML scopes each field to either the test_performed report
     or the test_results report (or both).
  2. Loads the two .docx templates from ``templates/`` — these are
     regular Word documents with Jinja2 placeholders, the kind a
     test engineer would maintain in Word / LibreOffice. Edit them,
     re-run, the report updates.
  3. Runs a battery of WARNING checks: ``check_value`` for
     register-style reads, ``check_value_in_range`` for "value
     must be inside a band" checks. Two of them pass
     ``operator="..."`` and ``seq_id="..."`` as ``**extras``; the
     YML declares ``operator`` (both reports) but not ``seq_id``,
     so ``seq_id`` is stored but never rendered. The register reads
     use ``radix=Radix.HEX``, so their value shows as ``0xDEAD`` in
     the log line *and* in the report.
  4. The user-supplied ``make_test_id`` from ``test_id_helpers.py``
     is handed to ``SegDocument(test_id_function=...)`` as a plain
     callable — no dotted path needed. It fills each
     ``CheckRecord.test_id`` (and the same id ends up in the log
     lines). The YML can point at the same function by dotted path
     instead; see the note at the bottom of ``hwval.yml``.
  5. Renders the two .docx outputs and prints the rendered text so
     the per-report field split and the missing-field defaulting to
     ``""`` are visible end-to-end.

Requires the optional ``hwval[docs]`` extra (docxtpl, python-docx,
jinja2, pyyaml).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

# Make ``test_id_helpers`` (next to this script) importable, and
# the repo root importable too so the YML's dotted-path form
# ("examples.08_test_id_and_yaml.test_id_helpers:make_test_id") can
# still be resolved if you prefer to drive it from the YAML.
sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
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
    Radix,
    SegDocument,
    check_value,
    check_value_in_range,
    reset_test_summary,
)

# The user-supplied test_id update function. It is handed to
# SegDocument below as a plain callable — the SegDocument constructor
# accepts either a callable or a "package.module:attr" string.
from test_id_helpers import make_test_id


HERE = Path(__file__).resolve().parent
CONFIG = HERE / "hwval.yml"

# The two .docx templates live next to the script. They are
# regular Word documents (Jinja2 placeholders inside paragraphs /
# tables), the kind a test engineer would maintain in Word or
# LibreOffice. ``build_templates.py`` regenerates the originals
# if you want to start over.
TEST_TEMPLATE = HERE / "templates" / "test_performed.docx"
RESULTS_TEMPLATE = HERE / "templates" / "test_results.docx"


def main() -> None:
    # Sanity-check the templates up front: a missing file is much
    # easier to diagnose here than deep inside docxtpl.
    for path in (TEST_TEMPLATE, RESULTS_TEMPLATE):
        if not path.is_file():
            sys.stderr.write(
                f"missing template: {path}\n"
                f"Run:  uv run python "
                f"{HERE / 'build_templates.py'}\n"
            )
            sys.exit(1)

    # --- 1. Run a battery of WARNING checks -----------------------
    # Some records pass `operator=` (declared in YML) and one
    # record also passes `seq_id=` (NOT declared in YML → stored
    # on the record but never rendered in the report).
    reset_test_summary()

    # --- 1a. check_value: register read-back style ----------------
    # ``radix=Radix.HEX`` makes the check print its operands in hex
    # — in the log line *and* in the generated report, so a register
    # value shows as 0xDEAD rather than 57005.
    check_value(0xDEAD, 0xDEAD, alert_level=AlertLevel.WARNING,
                msg="REG0 OK", scope="reg_walk", msg_id="ID_REG0",
                radix=Radix.HEX, operator="alice")
    check_value(0xBEEF, 0xCAFE, alert_level=AlertLevel.WARNING,
                msg="REG1 drift", scope="reg_walk", msg_id="ID_REG1",
                radix=Radix.HEX, operator="alice", seq_id="A1")
    check_value(0x1234, 0x1234, alert_level=AlertLevel.WARNING,
                msg="REG2 OK", scope="reg_walk", msg_id="ID_REG2",
                radix=Radix.HEX, operator="bob")
    # No `operator` here — it shows up as "" in the rendered
    # report (per the "missing field defaults to empty string"
    # contract).
    check_value(0x9999, 0x0001, alert_level=AlertLevel.WARNING,
                msg="REG3 mismatch", scope="reg_walk", msg_id="ID_REG3",
                radix=Radix.HEX)

    # --- 1b. check_value_in_range: "value must be inside a band" --
    check_value_in_range(
        1500, 0, 4095,
        alert_level=AlertLevel.WARNING,
        msg="ADC0 sample inside 12-bit band",
        scope="adc", msg_id="ID_ADC0",
        operator="alice",
    )
    check_value_in_range(
        5000, 0, 4095,
        alert_level=AlertLevel.WARNING,
        msg="ADC1 sample out of band (expected)",
        scope="adc", msg_id="ID_ADC1",
        operator="bob",
    )

    # --- 2. Build the SegDocument ---------------------------------
    # Templates are loaded from the path; layout comes from the YML
    # via the ``config=`` kwarg. Both are real on-disk files a
    # test engineer could open in Word.
    #
    # ``test_id_function=make_test_id`` passes the callable straight
    # in — no dotted path, no import gymnastics. An explicit kwarg
    # wins over the YML: the YML only fills in the keys the kwargs
    # left at their default, and ``test_id_function`` defaults to
    # ``None`` (= "not set"). Drop this line to let the YML decide
    # instead (see the note in ``hwval.yml``).
    doc = SegDocument(
        test_template=TEST_TEMPLATE,
        results_template=RESULTS_TEMPLATE,
        config=CONFIG,
        extra_context={"project": "Acme DUT v3", "operator": "alice"},
        test_id_function=make_test_id,
    )

    # --- 3. Render the two .docx files ----------------------------
    out_dir = HERE / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Keep a copy of the un-rendered template alongside the
    # rendered output for easy diffing in Word.
    shutil.copy(TEST_TEMPLATE, out_dir / "test_performed.docx")
    shutil.copy(RESULTS_TEMPLATE, out_dir / "test_results.docx")

    test_out, results_out = doc._generate(
        test_output=out_dir / "test_performed_OUT.docx",
        results_output=out_dir / "test_results_OUT.docx",
    )

    # --- 4. Print the rendered text --------------------------------
    print(f"templates: {TEST_TEMPLATE}")
    print(f"           {RESULTS_TEMPLATE}")
    print(f"rendered:  {test_out}")
    print(f"           {results_out}")
    for label, path in [("test performed", test_out),
                        ("test results", results_out)]:
        print(f"\n--- {label} ({path.name}) ---")
        rendered = Document(str(path))
        for p in rendered.paragraphs:
            if p.text.strip():
                print(p.text)


# --------------------------------------------------------------------------- #
# Editing the templates
# --------------------------------------------------------------------------- #
#
# The two .docx files in ``examples/08_test_id_and_yaml/templates/``
# are regular Word documents. Open them in Word or LibreOffice and
# edit the placeholders, headings, fonts, tables, footers, etc. —
# the Jinja / docxtpl syntax stays valid as long as you don't
# damage the placeholder text itself. Re-run ``example.py`` to see
# the change in the rendered output.
#
# The placeholders you can use are:
#
#   * ``{{ project }}``, ``{{ operator }}``,
#     ``{{ generated_at }}`` — from ``extra_context`` /
#     ``SegDocument`` internals.
#   * ``{{ summary.total }}`` / ``{{ summary.passed_count }}`` /
#     ``{{ summary.failed_count }}`` — record counts.
#   * ``{{ fields|join(', ') }}`` — the field names declared for
#     *this* report by the YML.
#   * ``{{ rec.<field> }}`` — every YML-declared field on a record
#     (``rec.test_id``, ``rec.scope``, ``rec.msg_id``,
#     ``rec.operator``, ``rec.value``, ``rec.expected``,
#     ``rec.passed``, ``rec.msg``, ``rec.detail``, …).
#
# Control tags (each on its own paragraph, exactly as written):
#
#   * ``{%p for rec in records %}`` — paragraph-level iteration
#     over every record. Each iteration becomes its own paragraph.
#   * ``{%p for rec in failed %}``  — same, but only failing records.
#   * ``{%p endfor %}``              — close the iteration.
#
# To start over from a clean starter, run:
#
#     uv run python examples/08_test_id_and_yaml/build_templates.py
#
# That regenerates the original two templates (overwriting any
# edits you made, so back up first if you want to keep them).


if __name__ == "__main__":
    main()

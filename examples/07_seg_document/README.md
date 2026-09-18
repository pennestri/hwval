# 07 · `SegDocument._generate` — docx reports

Render two `.docx` reports (test performed + test results) from
user-supplied Jinja2+docx templates. Each template is an ordinary Word
document containing `{{ ... }}` and `{%p ... %}` placeholders (docxtpl
syntax).

## Requirements

```bash
uv add hwval[docs]
# or
pip install hwval[docs]
```

This pulls in `docxtpl`, `python-docx`, and `jinja2`. The base library
stays dependency-free.

## Run

```bash
uv run python examples/07_seg_document/example.py
```

## What you'll see

```
rendered: .../examples/07_seg_document/out/test_performed_OUT.docx
rendered: .../examples/07_seg_document/out/test_results_OUT.docx

--- test performed (test_performed_OUT.docx) ---
Acme DUT v3 — Test Performed
Operator: alice
Generated: 2026-09-18T08:03:00+00:00
Tests performed: 4
  - [reg_walk] ID_REG0: REG0 OK
  - [reg_walk] ID_REG1: REG1 drift
  - [reg_walk] ID_REG2: REG2 OK
  - [reg_walk] ID_REG3: REG3 mismatch

--- test results (test_results_OUT.docx) ---
Acme DUT v3 — Test Results
Operator: alice
Total: 4    Passed: 2    Failed: 2
  - [reg_walk] ID_REG1: REG1 drift
      value=0xBEEF expected=0xCAFE  match=MATCH_STD
  - [reg_walk] ID_REG3: REG3 mismatch
      value=0x9999 expected=0x0001  match=MATCH_STD
```

The two `*_OUT.docx` files end up next to the templates under
`examples/07_seg_document/out/` so you can open them in a Word viewer
and see the rendered formatting.

## What it shows

| Step | Demonstrates                                                         |
| ---: | -------------------------------------------------------------------- |
| 1    | Building `.docx` templates programmatically via `python-docx`        |
| 2    | Running WARNING checks (the only level accumulated for reporting)     |
| 3    | Constructing `SegDocument(..., fields=..., filter=..., extra_context=...)` |
| 4    | `_generate(...)` returns the two output paths and writes both files  |

## Template syntax reminder

`{%p ... %}` is docxtpl's **paragraph-level** control — each iteration
becomes its own paragraph. If you want a table layout, build a Word
table in the template and use `{%tr ... %}` for row iteration.
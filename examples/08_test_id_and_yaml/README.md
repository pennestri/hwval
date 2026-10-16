# 08 · `test_id` field + YML-driven `SegDocument` config + per-report fields + `**extras`

Four things, all working together in this example:

1. **A `test_id` field on every WARNING-level `CheckRecord`.** The id
   comes from a user-supplied *update function* that sees the record
   and a 1-indexed sequence counter. The default emits a sequential
   `TID_<seq:04d>`; install your own with `set_test_id_function(...)`.
2. **A YAML config file for `SegDocument`.** The fields the report
   exposes, the include toggles, and the test-id update function can
   all live in a `hwval.yml` next to the test code. Edit the YAML,
   re-run, the report layout updates — no Python change required.
3. **Per-report field scoping.** Each field in the YML can be
   tagged with which report it appears in: `test_performed`,
   `test_results`, or both. The same `SegDocument` then drives two
   reports with different column sets.
4. **`**extras` on `check_value` / `check_value_in_range`.** Any
   kwarg whose name doesn't match a built-in parameter lands in
   `CheckRecord.extras`. YML-declared extras are surfaced in the
   report; undeclared ones are silently dropped. A YML-declared
   field that was *not* passed for a particular check shows up as
   the empty string in that row (per the "missing field defaults
   to empty string" contract).

## Requirements

```bash
uv add hwval[docs]
# or
pip install hwval[docs]
```

`hwval[docs]` pulls in `docxtpl`, `python-docx`, `jinja2`, **and
`pyyaml`** for the YAML config loader.

## Run

```bash
uv run python examples/08_test_id_and_yaml/example.py
```

## Files

```
examples/08_test_id_and_yaml/
├── README.md
├── example.py            # runs checks, loads templates, renders docs
├── build_templates.py    # regenerates the two .docx templates
├── hwval.yml             # drives the SegDocument config + per-report split
├── test_id_helpers.py    # the user-supplied test_id update function
├── templates/
│   ├── test_performed.docx   # loaded by example.py (test performed)
│   └── test_results.docx     # loaded by example.py (test results)
└── out/                  # rendered .docx files end up here
```

The two `.docx` files in `templates/` are regular Word documents
maintained in Word / LibreOffice. `example.py` loads them straight
from disk — there is no in-Python template builder. Open them in
Word, change the placeholders, fonts, tables, footers, … and
re-run `example.py` to see the change in the rendered output.
`build_templates.py` regenerates the originals.

## What it shows

| Step | Demonstrates                                                          |
| ---: | --------------------------------------------------------------------- |
| 1    | A user-supplied `test_id` function in `test_id_helpers.py`           |
| 2    | Per-field `reports` in `hwval.yml` (test_performed / test_results)    |
| 3    | `**extras` on `check_value` → land in `CheckRecord.extras`            |
| 4    | Loading the YAML via `SegDocument(..., config="hwval.yml")`           |
| 5    | Loading the two `.docx` templates from `templates/` by path          |
| 6    | Missing field in `extras` → renders as `""` in the report             |
| 7    | Both `check_value` *and* `check_value_in_range` in the same run       |

## YAML format

```yaml
# hwval.yml
fields:
  - test_id                                    # both reports (default)
  - name: msg_id
    reports: test_performed                    # only in test_performed
  - name: msg
    reports: test_results                      # only in test_results
  - name: detail
    reports: test_results
  - operator                                   # both reports

include_passed: true
include_failed: true

test_id_function: "examples.08_test_id_and_yaml.test_id_helpers:make_test_id"
```

- Each field is either a plain string (the field name; appears in
  *both* reports) or a mapping with `name` + `reports`.
- `reports` accepts:
  - a single string: `"all"`, `"test_performed"`, `"test_results"`.
  - a list of those strings.
- Omit `reports` (or use a plain string for the whole field) to
  default to "both reports".
- Any unknown top-level key is a hard error so typos surface
  immediately.
- Field names must be valid Python identifiers (they become Jinja
  attribute names inside the templates).

## test_id function shape

```python
def make_test_id(record, seq):
    return f"{record.scope}.{record.msg_id}.{seq:04d}"
```

The function sees the `CheckRecord` *before* `test_id` is filled in
(field is `""`) plus a 1-indexed counter that resets on
`reset_test_summary()`. It returns the new id as a string. Anything
the function can compute — hash, counter, scope+msg combo, time
prefix, … — is fair game.

## Extras from check_value

`check_value` / `check_value_in_range` accept arbitrary keyword
arguments after the named ones. They land on the record's
`extras` dict:

```python
check_value(
    0xDEAD, 0xDEAD,
    alert_level=AlertLevel.WARNING,
    msg="REG0 OK", scope="reg_walk", msg_id="ID_REG0",
    operator="alice",        # → extras["operator"] = "alice"
    # seq_id="A1",          # not in the YML → stored, never rendered
)
```

`scope`, `msg`, `msg_id`, `radix`, etc. are reserved (named
parameters of `check_value`); pass anything else and it shows up
in `extras`. The rendered report only displays fields listed in
the YML; a YML field that no record supplied shows as `""` in
that row.

## Editing the templates

The two `.docx` files in `templates/` are regular Word documents.
Open them in Word or LibreOffice and edit the placeholders,
headings, fonts, tables, footers, etc. — the Jinja / docxtpl
syntax stays valid as long as you don't damage the placeholder
text itself. Re-run `example.py` to see the change in the
rendered output.

The placeholders you can use:

| Placeholder                          | Source                                        |
| ------------------------------------ | --------------------------------------------- |
| `{{ project }}`, `{{ operator }}`    | `SegDocument(extra_context=...)`              |
| `{{ generated_at }}`                 | ISO 8601 UTC, set by `SegDocument._generate` |
| `{{ summary.total }}`                | total record count for the report             |
| `{{ summary.passed_count }}`         | passing record count                          |
| `{{ summary.failed_count }}`         | failing record count                          |
| `{{ fields|join(', ') }}`            | field names declared for this report          |
| `{{ rec.<field> }}`                  | every YML-declared field on each record       |

Control tags (each on its own paragraph, exactly as written):

| Tag                          | Effect                                                       |
| ---------------------------- | ------------------------------------------------------------ |
| `{%p for rec in records %}`  | paragraph-level iteration over every record                 |
| `{%p for rec in failed %}`   | same, but only failing records                               |
| `{%p endfor %}`              | close the iteration                                          |

To start over from a clean starter, run:

```bash
uv run python examples/08_test_id_and_yaml/build_templates.py
```

That regenerates the original two templates (overwriting any
edits you made, so back up first if you want to keep them).

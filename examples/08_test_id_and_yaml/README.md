# 08 · `test_id` field + YML-driven `SegDocument` config + per-report fields + `**extras`

Four things, all working together in this example:

1. **A `test_id` field on every WARNING-level `CheckRecord`.** The id
   comes from a user-supplied *update function* that sees the record
   and a 1-indexed sequence counter. The default emits a sequential
   `TID_<seq:04d>`; install your own with `set_test_id_function(...)`.
2. **A YAML config file for `SegDocument`.** The fields the report
   exposes and the include toggles can live in a `hwval.yml` next to
   the test code. Edit the YAML, re-run, the report layout updates
   — no Python change required. The test-id update function can live
   there too, but this example specifies it in Python instead (see
   *Specifying the test_id function* below).
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
| 5    | Passing the `test_id` function as a callable (`test_id_function=`)   |
| 6    | `radix=Radix.HEX` → the operands print as `0xDEAD` in the report      |
| 7    | Loading the two `.docx` templates from `templates/` by path          |
| 8    | Missing field in `extras` → renders as `""` in the report             |
| 9    | Both `check_value` *and* `check_value_in_range` in the same run       |

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

# test_id_function: "examples.08_test_id_and_yaml.test_id_helpers:make_test_id"
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

## Specifying the test_id function

There are two ways to tell `SegDocument` which function derives the
`test_id`, and this example uses the first one.

**1. In Python — a plain callable (used here).**

```python
from test_id_helpers import make_test_id          # next to example.py

doc = SegDocument(
    test_template=TEST_TEMPLATE,
    results_template=RESULTS_TEMPLATE,
    config=CONFIG,                                 # fields + toggles
    extra_context={"project": "Acme DUT v3", "operator": "alice"},
    test_id_function=make_test_id,                  # <- the callable
)
```

No dotted path, no import gymnastics — just import the function and
hand it over.

**2. In the YML — a `"package.module:attr"` string.**

```yaml
test_id_function: "examples.08_test_id_and_yaml.test_id_helpers:make_test_id"
```

Same convention as `logging.config.dictConfig` and `pickle`. The
string is resolved on `SegDocument` construction, so the module has
to be importable at that point.

**The kwarg wins.** The YML only fills in the keys the kwargs left
at their default, and `test_id_function` defaults to `None`
(= "not set"). So with both present, the callable passed in Python
is the one that gets installed — `hwval.yml` keeps its line
commented out so there is no ambiguity about which one is active.

A YML `test_id_function` must be a *string*: `load_seg_config`
rejects anything else with a `TypeError`. A callable is only
possible through the Python kwarg.

Either way the function is installed globally via
`set_test_id_function`, so the same id ends up in the report *and*
in the log lines emitted by `check_value`. Records that were already
in the accumulator are re-stamped, so it does not matter whether
the `SegDocument` is built before or after the checks run.

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

## The test performed report is chronological

The *test performed* document lists the checks in the order they ran,
each with its test id:

```
[reg_walk.ID_REG0.0001] … REG0 OK
[reg_walk.ID_REG1.0002] … REG1 drift
[reg_walk.ID_REG2.0003] … REG2 OK
```

The `records` list in the template context is ordered by the check
sequence (`CheckRecord.seq`) — not "all the passing ones first". The
*test results* document is different on purpose: it groups the failures
and the passes, because that is what a results report is about.

The sequence number is also available as a field, so you can number the
rows yourself:

```yaml
fields:
  - seq            # 1, 2, 3, … the order the checks ran in
  - test_id
  - msg
```

## The radix reaches the report

The register reads in `example.py` use `radix=Radix.HEX`:

```python
check_value(0xDEAD, 0xDEAD, alert_level=AlertLevel.WARNING,
            msg="REG0 OK", scope="reg_walk", msg_id="ID_REG0",
            radix=Radix.HEX, operator="alice")
```

The radix is not only a log-formatting knob — the generated report
prints the operands the same way, so the row reads
`value=0xDEAD expected=0xDEAD` in the `.docx` too, and the log line
and the report never disagree.

The record keeps the raw number (`rec.value` is still the int
`0xDEAD`); only the *rendered* value is formatted.

The ADC range check uses the default `Radix.DEC`, so its expected
stays readable: `in [0, 4095]`.

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

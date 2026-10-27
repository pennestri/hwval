# hwval

Structured assertion / check primitives for **hardware validation**. API is
inspired by UVVM's `check_value` and `check_value_in_range`
([uvvm.github.io](https://uvvm.github.io/utility_library.html#checks-and-awaits)),
ported to plain Python for use outside a VHDL simulator.

## Where to go next

- **Quick start + API reference:** keep reading this file.
- **Learn by example:** [examples/](examples/) — one focused subfolder
  per feature.
- **Project docs:** [docs/](docs/) — architecture, full API, extending,
  release process, and pre-generated `.docx` test reports.
- **Generate your own docx reports:** install `hwval[docs]` (see below)
  and see [examples/07_seg_document](examples/07_seg_document).

---

## Install

With [uv](https://docs.astral.sh/uv/):

```bash
uv add hwval
```

From a local checkout:

```bash
uv pip install -e .
```

To use `SegDocument` (Jinja2+docx report generation) install the optional
`docs` extra:

```bash
uv add hwval[docs]
# or
pip install hwval[docs]
```

### From a checkout placed inside another project

If the `hwval/` repo sits inside another uv project's `src/` folder,
wire it up as a **path dependency** — it stays a separate
distribution, but is imported as `hwval` and is editable:

```bash
cd myproject
uv add --editable ./src/hwval
# …or declaratively, in myproject/pyproject.toml:
```

```toml
[project]
dependencies = ["hwval[docs]"]          # the extra works over a path dep too

[tool.uv.sources]
hwval = { path = "src/hwval", editable = true }
```

Then `uv sync` and `from hwval import check_value` works — the
importable package lives at `src/hwval/src/hwval`, so the path to
point at is `src/hwval/src` (not `src/hwval`).

`uv add --editable` also adds the checkout to
`[tool.uv.workspace] members` automatically. To declare that
yourself:

```toml
[tool.uv.workspace]
members = ["src/hwval"]

[tool.uv.sources]
hwval = { workspace = true, editable = true }
```

Two other options:

* **Copy just the package** — copy `hwval/src/hwval/` to
  `myproject/src/hwval/`. A src-layout project puts `src/` on the
  path, so `from hwval import …` works with no config at all. The
  trade-off: `hwval` becomes part of *your* distribution (one
  version, no separate `docs` extra).
* **`PYTHONPATH`** — no config change at all:
  `PYTHONPATH=src/hwval/src uv run python …`.

One trap: keep the parent's
`[tool.hatch.build.targets.wheel] packages = ["src/<yourpkg>"]`
explicit. Without it, hatchling cannot work out what to ship when
`src/` holds a checkout whose directory name does not match the
project name, and the parent's wheel build fails.

---

## Quick start

```python
from hwval import AlertLevel, check_value, check_value_in_range

check_value(my_int, 42, msg="int must be 42")              # raises on mismatch
check_value_in_range(my_int, 0, 255, msg="byte range")     # raises on out-of-range
```

`check_value` and `check_value_in_range` return `True` on pass, `False` on
fail. At `*_ERROR` / `*_FAILURE` severity (default) they also raise
`AssertionError`. Lower severities only log.

---

## API reference

### `check_value(value, exp, *[, alert_level, msg, scope, msg_id, radix, match_strictness]) -> bool`

Compare `value` to `exp`.

| Parameter        | Type              | Default                       | Purpose                                  |
| ---------------- | ----------------- | ----------------------------- | ---------------------------------------- |
| `value`          | `Any`             | —                             | Value to check                           |
| `exp`            | `Any`             | —                             | Expected value                           |
| `alert_level`    | `AlertLevel`      | `AlertLevel.ERROR`            | Severity on mismatch                     |
| `msg`            | `str`             | `""`                          | Human-readable description              |
| `scope`          | `str`             | `"C_TB_SCOPE_DEFAULT"`        | Origin scope (logged)                    |
| `msg_id`         | `str`             | `"ID_POS_ACK"`                | Message identifier (logged)              |
| `radix`          | `Radix`           | `Radix.HEX_BIN_IF_INVALID`    | Display radix in log *and* in the generated report |
| `match_strictness` | `MatchStrictness` | `MatchStrictness.MATCH_STD`  | `MATCH_STD` (==) or `MATCH_EXACT` (==)   |

### `check_value_in_range(value, min_value, max_value, *[, alert_level, msg, scope, msg_id, radix]) -> bool`

Inclusive range check: `min_value <= value <= max_value`. Same severity /
log / raise behaviour as `check_value`.

### `set_logger(logger)`

Replace the module logger (`logging.getLogger("hwval")`). Useful in tests for
attaching a capturing handler.

### `SegDocument(test_template, results_template, *[, fields, include_passed, include_failed, filter, extra_context])`

Render two `.docx` test reports (one for *tests performed*, one for *test
results*) from user-supplied Jinja2+docx templates. Requires the
`hwval[docs]` extra (pulls in `docxtpl`, `python-docx`, `jinja2`,
and `pyyaml` for the YAML config loader below).

The class holds the two template paths plus the reporting options; the
actual rendering is done by `SegDocument._generate(...)`.

| Parameter           | Type                                | Default       | Purpose                                                       |
| ------------------- | ----------------------------------- | ------------- | ------------------------------------------------------------- |
| `test_template`     | `str` / `Path`                      | —             | Path to the *test performed* `.docx` template                 |
| `results_template`  | `str` / `Path`                      | —             | Path to the *test results* `.docx` template                   |
| `fields`            | `Sequence[str] \| Sequence[FieldSpec]` | every `DEFAULT_FIELDS` in both reports | Subset of fields exposed to the Jinja templates; each entry may be a plain string (field in both reports) or a `FieldSpec`/mapping to scope a field to one report (see §11) |
| `include_passed`    | `bool`                              | `True`        | Include passing records                                       |
| `include_failed`    | `bool`                              | `True`        | Include failing records                                       |
| `filter`            | `Callable[[CheckRecord], bool]`     | `None`        | Additional filter; runs after the include toggles             |
| `extra_context`     | `Mapping[str, Any]`                 | `{}`          | Extra keys merged into the Jinja context                      |
| `test_id_function`  | `callable` / `str` / `None`         | `None`        | Function used to derive `test_id` on every WARNING record    |
| `config`            | `str` / `Path` / `None`             | `None`        | YAML file driving any of the above keys (see below)           |

#### `SegDocument._generate(test_output, results_output, *, summary=None) -> Tuple[Path, Path]`

Render both templates and write them to disk. Returns the two output paths.

| Parameter        | Type                          | Default       | Purpose                                                       |
| ------------------ | ----------------------------- | ------------- | ------------------------------------------------------------- |
| `test_output`    | `str` / `Path`                | —             | Where to write the *test performed* document                 |
| `results_output` | `str` / `Path`                | —             | Where to write the *test results* document                   |
| `summary`        | `TestSummary \| None`         | accumulator   | Source of records; defaults to the current accumulator via `current_summary()` |

Both templates receive the **same** Jinja context, so the only difference
between the two documents is what you put in each template.

Available placeholders:

| Name              | Type                              | Meaning                                                |
| ----------------- | --------------------------------- | ------------------------------------------------------ |
| `summary`         | `TestSummary` (filtered)          | Counts + filtered `passed`/`failed` dicts              |
| `passed`          | `list[dict]`                      | Filtered passing records, projected onto `fields`      |
| `failed`          | `list[dict]`                      | Filtered failing records, projected onto `fields`      |
| `records`         | `list[dict]`                      | `passed + failed`                                      |
| `fields`          | `list[str]`                       | Echo of the field names (handy for header rows)        |
| `include_passed`  | `bool`                            | Echo of the toggle                                      |
| `include_failed`  | `bool`                            | Echo of the toggle                                      |
| `generated_at`    | `str` (ISO 8601 UTC)              | Render time                                             |
| anything else     | —                                 | From `extra_context`                                    |

Note: each `dict` only has the keys listed in `fields` — anything you
omit is invisible to the template, so this is also how you control what
appears in the report's tables.

The `value` and `expected` entries are rendered in the **radix the check
was made with**: a check made with `radix=Radix.HEX` shows `0x2A` in the
report, exactly like in the log line. The record itself keeps the raw
number (`rec.value` is still an `int`).

```python
check_value(0xDEAD, 0xDEAD, alert_level=AlertLevel.WARNING, radix=Radix.HEX)
# log line : value=0xDEAD expected=0xDEAD
# report   : value=0xDEAD expected=0xDEAD
```

### `report_test_summary(*, file=sys.stdout, reset=True, fail_on_failed=False) -> TestSummary`

Print and return a summary of every `WARNING` / `TB_WARNING` check observed
since the last reset (or process start). Each `check_value` and
`check_value_in_range` call at warning severity is recorded in module state
and surfaced here, both passing and failing.

| Parameter        | Type      | Default        | Purpose                                          |
| ---------------- | --------- | -------------- | ------------------------------------------------ |
| `file`           | `TextIO`  | `sys.stdout`   | Output stream. Pass `io.StringIO()` to capture.  |
| `reset`          | `bool`    | `True`         | Clear the accumulator after reporting.           |
| `fail_on_failed` | `bool`    | `False`        | Raise `AssertionError` if any WARNING failed.    |

The returned `TestSummary` exposes `passed`, `failed` (`list[CheckRecord]`),
`passed_count`, `failed_count`, `total`, and an `ok` convenience flag.

### `reset_test_summary()`

Clear the WARNING-test summary accumulator. Useful in test fixtures to start
each case from a clean slate.

### `CheckRecord` / `TestSummary` / `FieldSpec`

Dataclasses returned by the summary API.

```python
@dataclass(frozen=True)
class CheckRecord:
    scope: str
    msg_id: str
    msg: str
    passed: bool = True          # default = "no failure reported"
    detail: str = ""             # one-liner produced by _emit
    test_id: str = ""            # populated by the user-supplied test_id_function
    extras: Mapping[str, Any] = field(default_factory=dict)  # **kwargs
    value: Any = None            # the operand the check compared
    expected: Any = None         # the literal target / "in [min, max]"

@dataclass
class TestSummary:
    passed: List[CheckRecord]
    failed: List[CheckRecord]
    # properties: passed_count, failed_count, total, ok

@dataclass(frozen=True)
class FieldSpec:
    name: str
    reports: tuple[str, ...] = ("test_performed", "test_results")
```

`value` and `expected` are stored on the record when a `check_*`
runs and become available in the rendered report (declare them in
the YML like any other field). `extras` is where `**kwargs`
passed to `check_value` / `check_value_in_range` land (see
[§12](#12-pass-extras-to-check_-for-yml-declared-fields)).
`FieldSpec` is the per-field record used by `SegDocument.fields`
to control which report(s) each field appears in.

### `set_test_id_function(func=None)`, `get_test_id_function() -> callable`

Install / inspect the function used to derive `test_id` on every
WARNING-level `CheckRecord`. See [§10](#10-test_id-field--user-supplied-update-function).
The default function (returned until you install your own) emits
`"TID_<seq:04d>"`. Passing `None` restores the default.

### `load_seg_config(path) -> dict`

Load a `SegDocument` configuration from a YAML file. See
[§11](#11-drive-the-segdocument-config-from-yaml). Raises
`ImportError` if PyYAML is not installed, `FileNotFoundError` if the
path is missing, `ValueError` on unknown keys, `TypeError` on
wrong-typed values.

### Enums

```python
class AlertLevel(Enum):
    TB_FAILURE, FAILURE              # log CRITICAL, raise AssertionError
    TB_ERROR,   ERROR                # log ERROR,     raise AssertionError
    TB_WARNING, WARNING              # log WARNING,   no raise
    NOTE,       INFO                 # log INFO,      no raise
    DEBUG,      LOGICAL              # log DEBUG,     no raise

class MatchStrictness(Enum):
    MATCH_STD                         # `==` comparison (UVVM `std_match`)
    MATCH_EXACT                       # strict `==` (UVVM `=`)

class Radix(Enum):
    HEX, BIN, DEC, OCT
    UNSIGNED, SIGNED, ASCII
    HEX_BIN_IF_INVALID                 # default for check_value
```

---

## Practical examples

### 1. Basic register read check

After writing `0xDEADBEEF` to a register, verify the read-back matches.

```python
from hwval import AlertLevel, check_value, Radix

def test_reg_readback(dut):
    dut.reg.write(0xDEAD_BEEF)
    readback = dut.reg.read()
    check_value(
        readback,
        0xDEAD_BEEF,
        msg="REG32 must read back the value just written",
        scope="reg_model",
        msg_id="ID_REG_RD",
        radix=Radix.HEX,
    )
```

### 2. Status register bit-field check

A status register reports bits per field. Verify each field independently
without halting on the first failure.

```python
from hwval import AlertLevel, check_value

STATUS = {"ready": 1 << 0, "error": 1 << 1, "mode": 0b11 << 2}

def test_status_after_init(dut):
    s = dut.status.read()
    check_value(s & STATUS["ready"], STATUS["ready"],
                alert_level=AlertLevel.ERROR, msg="READY bit must be set")
    check_value(s & STATUS["error"], 0,
                alert_level=AlertLevel.ERROR, msg="ERROR bit must be clear")
    check_value((s & STATUS["mode"]) >> 2, 0b10,
                alert_level=AlertLevel.WARNING, msg="MODE default is 0b10")
```

Using `WARNING` for the mode field means the test continues and you get a
full picture of all mismatches in one run.

### 3. Range check on a measured value

```python
from hwval import check_value_in_range, AlertLevel

def test_adc_sample_in_range(dut):
    sample = dut.adc.read()
    check_value_in_range(
        sample,
        min_value=2000,
        max_value=3000,
        alert_level=AlertLevel.TB_ERROR,
        msg="ADC sample must fall in the expected band",
        scope="adc_checker",
    )
```

### 4. Soft-fail with `WARNING`

When a check is informational and shouldn't fail the test:

```python
from hwval import AlertLevel, check_value

def test_drift_within_margin(dut):
    drift = dut.counter.read() - dut.counter_baseline.read()
    if not check_value(
        abs(drift),
        0,
        alert_level=AlertLevel.WARNING,
        msg="drift > 0 — investigate",
    ):
        log.warning("counter drift = %d", drift)
```

### 5. Capture log output in pytest

The library logs to `logging.getLogger("hwval")`. Use pytest's `caplog` to
assert on the log line itself:

```python
import logging
from hwval import check_value, AlertLevel

def test_log_message_is_emitted(caplog):
    caplog.set_level(logging.INFO, logger="hwval")
    check_value(1, 2, alert_level=AlertLevel.WARNING, msg="captured")
    assert any("captured" in r.message and r.levelno == logging.WARNING
               for r in caplog.records)
```

### 6. Replace the logger globally

For test harnesses that prefer their own logger:

```python
import logging
from hwval import set_logger, check_value

harness_log = logging.getLogger("my_harness")
set_logger(harness_log)
check_value(1, 1, msg="now routed to my_harness")
```

### 7. Sweep of values

```python
from hwval import check_value_in_range, AlertLevel

def test_loopback_full_range(dut):
    for stimulus in range(0, 256):
        dut.bus.write(stimulus)
        observed = dut.bus.read()
        check_value(
            observed,
            stimulus,
            alert_level=AlertLevel.TB_ERROR,
            msg=f"loopback failed at stimulus=0x{stimulus:02X}",
            radix=Radix.HEX,
        )
```

The first mismatch raises `AssertionError`, so the loop aborts at the
earliest failure with a clear message.

### 8. Summarise every WARNING check with `report_test_summary`

WARNING-level checks don't raise, so a single mismatch is silent. Use
`report_test_summary()` at the end of a test (or session) to see every
WARNING check that ran — both passing and failing.

```python
from hwval import (
    AlertLevel,
    check_value,
    check_value_in_range,
    report_test_summary,
    reset_test_summary,
)

def test_register_walk(dut):
    reset_test_summary()  # start with a clean accumulator

    for reg in dut.registers:
        value = dut.bus.read(reg)
        check_value(
            value, reg.expected,
            alert_level=AlertLevel.WARNING,
            msg=f"{reg.name} read-back",
            scope="reg_walk",
            msg_id="ID_REG_WALK",
        )
        check_value_in_range(
            value, 0, 0xFFFF,
            alert_level=AlertLevel.WARNING,
            msg=f"{reg.name} range",
        )

    summary = report_test_summary()
    assert summary.ok, f"{summary.failed_count} WARNING check(s) failed"
```

Output looks like:

```
Test Summary: 7 passed, 2 failed

FAILED (2):
  [reg_walk] ID_REG_WALK REG07 read-back
      value=5 expected=8
  [C_TB_SCOPE_DEFAULT] ID_POS_ACK REG12 range
      value=70000 expected=in [0, 65535]

PASSED (7):
  [reg_walk] ID_REG_WALK REG00 read-back
      value=0 expected=0
  ...
```

For pytest fixtures, put `reset_test_summary()` in `setUp` so each test
starts with a fresh accumulator. Use `fail_on_failed=True` to turn a
non-zero summary into a regular test failure.

### 9. Generate docx reports with `SegDocument`

Render a pair of Word documents (test performed + test results) from
Jinja2+docx templates. The user supplies both `.docx` templates, and the
library fills in the records.

```python
from hwval import SegDocument

doc = SegDocument(
    test_template="templates/test_performed.docx",
    results_template="templates/test_results.docx",
    fields=("msg", "scope", "msg_id", "passed", "detail"),
    filter=lambda r: r.scope == "reg_walk",          # only reg_walk records
    include_failed=True,
    extra_context={"project": "Acme DUT v3", "operator": "alice"},
)

test_path, results_path = doc._generate(
    test_output="out/test_performed.docx",
    results_output="out/test_results.docx",
)
```

A *test performed* template body might look like:

```
Project: {{ project }}
Operator: {{ operator }}
Generated: {{ generated_at }}

Tests performed: {{ summary.total }}
{%p for rec in records %}{{ rec.msg_id }} — {{ rec.scope }}: {{ rec.msg }}
{%p endfor %}
```

A *test results* template body might look like:

```
Total: {{ summary.total }}  Passed: {{ summary.passed_count }}  Failed: {{ summary.failed_count }}
{%p for rec in failed %}{{ rec.msg_id }} — {{ rec.msg }}
    {{ rec.detail }}
{%p endfor %}
```

`{%p ... %}` is docxtpl's paragraph-level control: the loop body becomes
one paragraph per record. If you want table-style output, build a Word
table in your template and use `{%tr ... %}` (column iteration) instead.

### 10. `test_id` field + user-supplied update function

Every WARNING-level `CheckRecord` carries a `test_id` string. The
default is sequential (`TID_0001`, `TID_0002`, ...); the 1-indexed
counter resets whenever `reset_test_summary()` or
`report_test_summary(reset=True)` runs. Install your own function
with `set_test_id_function(fn)` — it gets the record (with
`test_id=""`) and the 1-indexed `seq`, and returns the new id:

```python
from hwval import set_test_id_function

def make_test_id(record, seq):
    return f"{record.scope}.{record.msg_id}.{seq:04d}"

set_test_id_function(make_test_id)
```

After this every WARNING record — past, present, and future — has a
test_id of the form `reg_walk.ID_REG0.0001`. The function is
re-stamped onto existing records when you swap it, so the whole
accumulator stays consistent with whichever function is currently
active. A buggy function never breaks a check: the failure is caught,
a DEBUG log line is emitted, and the default function takes over for
that one record.

### 11. Drive the `SegDocument` config from YAML

`SegDocument` accepts a `config=` keyword that points at a YAML
file. The YAML holds the same keys the constructor does
(`fields`, `include_passed`, `include_failed`, `test_id_function`);
explicit kwargs always win over the YAML, so the file is a
convenience layer rather than a hard override. Unknown keys raise
`ValueError` so typos surface immediately.

`hwval.yml`:

```yaml
fields:
  - test_id
  - name: msg_id
    reports: test_performed      # only in test_performed
  - name: msg
    reports: test_results        # only in test_results
  - name: detail
    reports: test_results
  - scope
  - passed
  - operator                     # both reports (default)
include_passed: true
include_failed: true
test_id_function: "my_pkg.test_id_helpers:make_test_id"
```

```python
from hwval import SegDocument

doc = SegDocument(
    test_template="templates/test_performed.docx",
    results_template="templates/test_results.docx",
    config="hwval.yml",
    extra_context={"project": "Acme DUT v3", "operator": "alice"},
)
```

Each `fields` entry is either a plain string (the field name; the
field appears in **both** rendered reports) or a mapping with
`name` + `reports` keys. `reports` accepts `"test_performed"`,
`"test_results"`, or `"all"`, either as a single string or a list.
Field names must be valid Python identifiers (they become Jinja
attribute names inside the templates).

`test_id_function` follows the same `"package.module:attr"`
convention as `logging.config.dictConfig` and `pickle`. It is
resolved when `SegDocument` is constructed and installed globally
via `set_test_id_function` so the same id ends up in the log lines
emitted by `check_value` as well.

The YML can only hold that *string* form. To hand over a callable
directly, pass it as a kwarg — an explicit kwarg always wins over
the YAML, so the file can still hold the fields and the toggles:

```python
from my_pkg.test_id_helpers import make_test_id

doc = SegDocument(
    test_template="templates/test_performed.docx",
    results_template="templates/test_results.docx",
    config="hwval.yml",              # fields + toggles from the file
    test_id_function=make_test_id,   # the callable, in Python
)
```

Working example: [examples/08_test_id_and_yaml](examples/08_test_id_and_yaml).

### 12. Pass `**extras` to `check_*` for YML-declared fields

A WARNING-level `CheckRecord` carries an `extras: Mapping[str, Any]`
dict. `check_value` / `check_value_in_range` accept any keyword
argument whose name doesn't collide with a named parameter, and
those kwargs land in `extras`:

```python
check_value(
    0xDEAD, 0xDEAD,
    alert_level=AlertLevel.WARNING,
    msg="REG0 OK", scope="reg_walk", msg_id="ID_REG0",
    operator="alice",       # → extras["operator"] = "alice"
    retries=3,              # → extras["retries"]  = 3
)
```

YML-declared extras (e.g. `operator` in the snippet above) are
surfaced in the rendered report. Extras that are not declared in
the YML are silently dropped from the report (but still live on
the record). A YML field that was *not* supplied for a particular
check shows up as the empty string in that row — that is the
"default for unspecified fields" contract:

```
| test_id                | msg     | operator |
|------------------------|---------|----------|
| reg_walk.ID_REG0.0001  | REG0 OK | alice    |
| reg_walk.ID_REG3.0004  | REG3…   |          |   # no operator → ""
```

Field names that match a built-in `CheckRecord` attribute
(`scope`, `msg`, `msg_id`, `passed`, `detail`, `test_id`) are
reserved: pass them as the named parameter to populate the
built-in. (If you really need a same-named extra, the record can
still be built directly via `CheckRecord(extras=...)`, but the
projection prefers `extras` over the built-in when both are set.)

### 13. Build the YML with a GUI

Two complementary GUIs are shipped under [`tools/`](tools/):

* [`tools/seg_config_gui/`](tools/seg_config_gui/) — a
  self-contained HTML/JS form. No dependencies, no server: open
  the file in a browser and start clicking.
* [`tools/seg_config_gui_flask/`](tools/seg_config_gui_flask/) —
  a pure-Python Flask app. The YML is generated and validated on
  the server (via the same `hwval.docs.load_seg_config` the
  real `SegDocument` constructor uses), so a green "valid" badge
  means the YML will load without error. Useful for central
  deployment and for projects that want the validation to live
  in one place.

```bash
# Static HTML GUI
xdg-open tools/seg_config_gui/index.html

# Flask GUI
uv sync --extra docs
uv run python tools/seg_config_gui_flask/app.py
# …then open http://127.0.0.1:5000/
```

Both let you add, remove and reorder fields, scope each field
to `test_performed`, `test_results`, or both, pick the
`include_passed` / `include_failed` toggles, and set the
`test_id_function` dotted path. Field names are validated as
Python identifiers, duplicates are rejected, and the
`test_id_function` is checked for the `"package.module:attr"`
shape. The Flask GUI also exposes a *Download hwval.yml* button
that posts the same form state to `/download` and saves the
response as a file. See the per-tool READMEs.

The Flask GUI additionally

* takes an `extra_context` mapping (key/value pairs, validated as
  Python identifiers) that is merged into the Jinja context by
  `SegDocument(extra_context=...)` — it is shown in the Python-kwargs
  preview rather than in the YML, because `load_seg_config` only
  accepts `fields`, `include_passed`, `include_failed` and
  `test_id_function`;
* loads an existing `hwval.yml` back into the form (upload the file
  at the top of the page). The upload is validated with the real
  `load_seg_config`, so a file that loads in the GUI is a file that
  works at runtime;
* generates the two starter `.docx` templates
  (`test_performed.docx` + `test_results.docx`) that
  `SegDocument` consumes, pre-filled with the fields you declared
  (scoped to that report) and a `{{ <key> }}` placeholder for every
  extra-context key. Download them with the *Download
  test_performed.docx* / *Download test_results.docx* buttons, open
  them in Word and adjust the layout.

---

## Severity reference

| AlertLevel          | Python log level | On FAIL            |
| ------------------- | ---------------- | ------------------ |
| `TB_FAILURE`        | `CRITICAL`       | raise + log        |
| `FAILURE`           | `CRITICAL`       | raise + log        |
| `TB_ERROR`          | `ERROR`          | raise + log        |
| `ERROR`             | `ERROR`          | raise + log        |
| `TB_WARNING`        | `WARNING`        | log only           |
| `WARNING`           | `WARNING`        | log only           |
| `NOTE` / `INFO`     | `INFO`           | log only           |
| `DEBUG` / `LOGICAL` | `DEBUG`          | log only           |

---

## Not ported (need a VHDL simulator)

`check_stable`, `await_change`, `await_value`, `check_sb_completion` —
all require VHDL simulation time or scoreboard state. They are stubs that
raise `NotImplementedError`. Port to cocotb if you need them.

---

## Development

```bash
uv sync --extra docs   # one-time venv + dev deps + docs extra
uv run pytest     # 120 tests

# Run the example scripts (one per feature)
for d in examples/0?_*/; do uv run python "$d/example.py"; done

# Regenerate the project-level docx test reports
uv run python docs/generated/generate.py
```

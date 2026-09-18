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
| `radix`          | `Radix`           | `Radix.HEX_BIN_IF_INVALID`    | Display radix in log                     |
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
`hwval[docs]` extra (pulls in `docxtpl`).

The class holds the two template paths plus the reporting options; the
actual rendering is done by `SegDocument._generate(...)`.

| Parameter           | Type                                | Default       | Purpose                                                       |
| ------------------- | ----------------------------------- | ------------- | ------------------------------------------------------------- |
| `test_template`     | `str` / `Path`                      | —             | Path to the *test performed* `.docx` template                 |
| `results_template`  | `str` / `Path`                      | —             | Path to the *test results* `.docx` template                   |
| `fields`            | `Sequence[str]`                     | all fields    | Subset of `CheckRecord` fields exposed to Jinja templates    |
| `include_passed`    | `bool`                              | `True`        | Include passing records                                       |
| `include_failed`    | `bool`                              | `True`        | Include failing records                                       |
| `filter`            | `Callable[[CheckRecord], bool]`     | `None`        | Additional filter; runs after the include toggles             |
| `extra_context`     | `Mapping[str, Any]`                 | `{}`          | Extra keys merged into the Jinja context                      |

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

### `CheckRecord` / `TestSummary`

Dataclasses returned by the summary API.

```python
@dataclass(frozen=True)
class CheckRecord:
    scope: str
    msg_id: str
    msg: str
    passed: bool
    detail: str

@dataclass
class TestSummary:
    passed: List[CheckRecord]
    failed: List[CheckRecord]
    # properties: passed_count, failed_count, total, ok
```

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
uv sync           # one-time venv + dev deps
uv run pytest     # 42 tests

# Run the example scripts (one per feature)
for d in examples/0?_*/; do uv run python "$d/example.py"; done

# Regenerate the project-level docx test reports
uv run python docs/generated/generate.py
```

# Public API reference

This is the canonical reference for every symbol exported from the
`hwval` package. The [`README.md`](../README.md) at the repo root is a
narrative tour; this file is exhaustive.

## Module-level

### `check_value`

```python
def check_value(
    value: Any,
    exp: Any,
    *args: Any,
    alert_level: AlertLevel = AlertLevel.ERROR,
    msg: str = "",
    scope: str = "C_TB_SCOPE_DEFAULT",
    msg_id: str = "ID_POS_ACK",
    radix: Radix = Radix.HEX_BIN_IF_INVALID,
    match_strictness: MatchStrictness = MatchStrictness.MATCH_STD,
) -> bool: ...
```

Compare `value` to `exp`. Returns `True` on pass, `False` on fail. On
FAIL with a severity in `_RAISING_LEVELS` (`TB_FAILURE`, `FAILURE`,
`TB_ERROR`, `ERROR`) also raises `AssertionError`.

Positional extra args: if the first positional after `exp` is a
`MatchStrictness`, it is consumed as `match_strictness` (UVVM
compatibility). Any other positional arg raises `TypeError`.

### `check_value_in_range`

```python
def check_value_in_range(
    value: Any,
    min_value: Any,
    max_value: Any,
    *args: Any,
    alert_level: AlertLevel = AlertLevel.ERROR,
    msg: str = "",
    scope: str = "C_TB_SCOPE_DEFAULT",
    msg_id: str = "ID_POS_ACK",
    radix: Radix = Radix.DEC,
) -> bool: ...
```

Inclusive range check: `min_value <= value <= max_value`. Same severity
/ log / raise semantics as `check_value`.

### `set_logger`

```python
def set_logger(logger: logging.Logger) -> None: ...
```

Replace the module logger. Default is `logging.getLogger("hwval")`.
Useful for tests or for routing logs into a host application's logger
hierarchy.

### `report_test_summary`

```python
def report_test_summary(
    *,
    file: Optional[TextIO] = None,
    reset: bool = True,
    fail_on_failed: bool = False,
) -> TestSummary: ...
```

Print and return a summary of every `WARNING` / `TB_WARNING` check
observed since the last reset. By default clears the accumulator
(`reset=True`). `fail_on_failed=True` raises `AssertionError` if any
recorded WARNING failed.

### `reset_test_summary`

```python
def reset_test_summary() -> None: ...
```

Clear the WARNING-test summary accumulator without printing. Useful in
test fixtures.

### `current_summary`

```python
def current_summary() -> TestSummary: ...
```

Return a non-destructive snapshot of the current accumulator as a
`TestSummary`. Used internally by `SegDocument._generate` so generating
a report doesn't consume the accumulator.

## Classes / dataclasses

### `class AlertLevel(Enum)`

UVVM-style severity, mapped to stdlib logging levels:

| Member      | Python log level | Raises `AssertionError` on FAIL |
| ----------- | ---------------- | ------------------------------- |
| `TB_FAILURE` | `CRITICAL`       | yes                             |
| `FAILURE`    | `CRITICAL`       | yes                             |
| `TB_ERROR`   | `ERROR`          | yes                             |
| `ERROR`      | `ERROR`          | yes                             |
| `TB_WARNING` | `WARNING`        | no                              |
| `WARNING`    | `WARNING`        | no                              |
| `NOTE`       | `INFO`           | no                              |
| `INFO`       | `INFO`           | no                              |
| `DEBUG`      | `DEBUG`          | no                              |
| `LOGICAL`    | `DEBUG`          | no                              |

### `class MatchStrictness(Enum)`

| Member        | Meaning                                              |
| ------------- | ---------------------------------------------------- |
| `MATCH_STD`   | `==` comparison (UVVM `std_match`, `'H' == '1'`)     |
| `MATCH_EXACT` | strict `==` (UVVM `=`)                                |

### `class Radix(Enum)`

Display radix for log formatting:

| Member                  | Meaning                                |
| ----------------------- | -------------------------------------- |
| `HEX`, `BIN`, `DEC`, `OCT` | fixed numeric base                  |
| `UNSIGNED`, `SIGNED`, `ASCII` | alternate scalar formats        |
| `HEX_BIN_IF_INVALID`    | default for `check_value`: hex/bin for ints, raw for others |

### `class CheckRecord`

Frozen dataclass representing one WARNING-level check outcome:

```python
@dataclass(frozen=True)
class CheckRecord:
    scope: str
    msg_id: str
    msg: str
    passed: bool
    detail: str
```

### `class TestSummary`

Dataclass returned by `report_test_summary` and `current_summary`:

```python
@dataclass
class TestSummary:
    passed: list[CheckRecord]   # filtered, projected onto `fields` if from SegDocument
    failed: list[CheckRecord]

    # properties:
    total         # len(passed) + len(failed)
    passed_count  # len(passed)
    failed_count  # len(failed)
    ok            # not self.failed
```

In SegDocument's Jinja context, `summary.passed`/`summary.failed` are
plain dicts projected onto the user-configured `fields`; counts and
`total` reflect what's actually in the rendered document.

### `class SegDocument` *(optional `hwval[docs]`)*

```python
class SegDocument(
    test_template, results_template, *,
    fields=("msg", "scope", "msg_id", "passed", "detail"),
    include_passed=True,
    include_failed=True,
    filter=None,
    extra_context=None,
):
    def _generate(
        test_output, results_output, *,
        summary=None,
    ) -> Tuple[Path, Path]: ...
```

Binds two `.docx` templates plus reporting options. Templates are
ordinary Word documents containing Jinja placeholders, processed via
[`docxtpl`](https://docxtpl.readthedocs.io/).

Jinja context available to both templates:

| Name              | Type                              |
| ----------------- | --------------------------------- |
| `summary`         | `TestSummary` (filtered, projected to dicts) |
| `passed`          | `list[dict]`                      |
| `failed`          | `list[dict]`                      |
| `records`         | `list[dict]` (`passed + failed`)  |
| `fields`          | `list[str]`                       |
| `include_passed`  | `bool`                            |
| `include_failed`  | `bool`                            |
| `generated_at`    | `str` (ISO 8601 UTC)              |
| `extra_context`   | whatever you passed in            |

`_generate()` does **not** clear the accumulator — it uses
`current_summary()` to peek.

Raises `ImportError` on construction if `docxtpl` isn't installed.

## Stubs (raise `NotImplementedError`)

| Function                | Reason                                       |
| ----------------------- | -------------------------------------------- |
| `check_stable`          | needs VHDL simulation time                   |
| `check_sb_completion`   | UVVM-specific scoreboard concept             |
| `await_change`          | needs VHDL simulation time                   |
| `await_value`           | needs VHDL simulation time                   |

Port to [cocotb](https://www.cocotb.org/) if you need these in a Python
HDL testbench.
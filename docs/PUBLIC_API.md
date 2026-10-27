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

### `set_test_id_function` / `get_test_id_function`

```python
TestIdFunction = Callable[[CheckRecord, int], str]

def set_test_id_function(
    func: Optional[TestIdFunction] = None,
) -> None: ...

def get_test_id_function() -> TestIdFunction: ...
```

Install (or clear) the function used to derive `test_id` on every
WARNING-level `CheckRecord`. The function receives the record (with
`test_id == ""`) and a 1-indexed sequence number, and returns the
new id string. When the function is *changed*, every record already
in the accumulator is re-stamped with the new function (each
record keeps its 1-indexed position). Passing `None` to
`set_test_id_function` restores the default
`"TID_<seq:04d>"` function.

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
    passed: bool = True            # default = "no failure reported"
    detail: str = ""               # one-liner produced by _emit
    test_id: str = ""              # populated by set_test_id_function
    extras: Mapping[str, Any] = field(default_factory=dict)
    value: Any = None              # the operand the check compared
    expected: Any = None           # the literal target / "in [min, max]"
    radix: Radix = Radix.DEC       # the display radix of the check
```

`test_id` is filled in by the active test_id function (see
`set_test_id_function` above). `value` and `expected` are the
operands the check compared — `expected` is the literal target
for `check_value` and the `"in [min, max]"` string for
`check_value_in_range`. Both default to `None` so a `CheckRecord`
can be built without them (e.g. for a pure "this happened" marker
without a value). `extras` carries any user-supplied YML-declared
fields passed as ``**kwargs`` to :func:`hwval.check_value` /
:func:`hwval.check_value_in_range`; the YML decides whether each
extra is rendered (and in which report).

`radix` remembers the display radix the check was made with, so the
generated report prints the numbers the way the log line did — a check
made with `radix=Radix.HEX` shows `0x2A` in the report, not `42`. Use
`record.format_radix(value)` to render a value that way yourself.

### `format_value(value, radix) -> str`

Format a value the way a check with that radix would print it:
integers in the requested radix (`0x2A`, `0b101010`, `0o52`),
booleans as `1` / `0`, sequences as a MSB-first vector. This is the
formatting used in the log lines, in `CheckRecord.detail` and — through
`CheckRecord.format_radix` — in the generated docx report.

### `class FieldSpec`

Per-field record used by `SegDocument.fields` to control which
report(s) each field appears in:

```python
@dataclass(frozen=True)
class FieldSpec:
    name: str
    reports: tuple[str, ...] = ("test_performed", "test_results")
```

`reports` may include `"test_performed"`, `"test_results"`, or
`"all"` (an alias for both). A field is rendered only in reports
listed in its `reports` tuple. :meth:`FieldSpec.coerce` normalises
plain strings, dicts, and existing `FieldSpec` objects into a
canonical `FieldSpec`.

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
    fields=None,               # str | FieldSpec | mapping per field
    include_passed=True,
    include_failed=True,
    filter=None,
    extra_context=None,
    test_id_function=None,     # callable or "package.module:attr" string
    config=None,               # path to a YAML config file
):
    def _generate(
        test_output, results_output, *,
        summary=None,
    ) -> Tuple[Path, Path]: ...
```

Binds two `.docx` templates plus reporting options. Templates are
ordinary Word documents containing Jinja placeholders, processed via
[`docxtpl`](https://docxtpl.readthedocs.io/).

`fields` is a sequence of `FieldSpec` (or anything
`FieldSpec.coerce` accepts). Each entry is a string (the field name
appears in **both** reports) or a `FieldSpec` / dict that scopes the
field to a subset of reports:

```python
SegDocument(
    test_template=...,
    results_template=...,
    fields=[
        "test_id",                                    # both reports
        {"name": "msg_id", "reports": "test_performed"},
        {"name": "msg",    "reports": "test_results"},
        {"name": "detail", "reports": "test_results"},
    ],
)
```

When `test_id_function` is supplied it is installed globally via
`set_test_id_function` so the same id ends up in logs and reports.
When `config=` points at a YAML file the listed keys
(`fields`, `include_passed`, `include_failed`, `test_id_function`)
fill in any kwargs the caller left at their default; explicit
kwargs always win over the YAML. Each template receives a
per-report filtered Jinja context — the `fields` placeholder
inside a template therefore lists exactly the columns the
corresponding report will render.

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

### `load_seg_config` *(optional `hwval[docs]`)*

```python
def load_seg_config(path: Union[str, Path]) -> dict: ...
```

Load a `SegDocument` configuration from a YAML file. Validated keys:

| Key                | Type        | Default | Notes                                                |
| ------------------ | ----------- | ------- | ---------------------------------------------------- |
| `fields`           | list        | (defaults) | Field names / specs exposed to templates. Each entry is a plain string (field in both reports) or a mapping with `name` + `reports` keys. |
| `include_passed`   | bool        | `True`  | Include passing records in the report                |
| `include_failed`   | bool        | `True`  | Include failing records in the report                |
| `test_id_function` | str         | —       | `"package.module:attr"` reference to a `(record, seq) -> str` function |

`fields[*].reports` is a string or list of strings chosen from
`"test_performed"`, `"test_results"`, or `"all"`. The returned
dict holds a normalised `fields` value: a list of `FieldSpec`
objects. Field names must be valid Python identifiers (they become
Jinja attribute names in the templates).

Unknown top-level keys raise `ValueError`. Wrong-typed values
raise `TypeError`. Duplicate field names raise `ValueError`.
Requires PyYAML; raises `ImportError` otherwise. The YAML only
fills in keys the caller did not already pass to `SegDocument`
explicitly, so the constructor signature is the source of truth
and the YAML is a convenience layer.

## Stubs (raise `NotImplementedError`)

| Function                | Reason                                       |
| ----------------------- | -------------------------------------------- |
| `check_stable`          | needs VHDL simulation time                   |
| `check_sb_completion`   | UVVM-specific scoreboard concept             |
| `await_change`          | needs VHDL simulation time                   |
| `await_value`           | needs VHDL simulation time                   |

Port to [cocotb](https://www.cocotb.org/) if you need these in a Python
HDL testbench.
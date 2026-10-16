# Extending `hwval`

Common extensions, with code sketches.

## Add a new check primitive

`check_value` and `check_value_in_range` both delegate to `_emit()`. To
add a third primitive — say, a bit-mask check — do the same:

```python
# in checks.py
def check_value_masked(
    value: int,
    mask: int,
    exp: int,
    *,
    alert_level: AlertLevel = AlertLevel.ERROR,
    msg: str = "",
    scope: str = "C_TB_SCOPE_DEFAULT",
    msg_id: str = "ID_POS_ACK",
) -> bool:
    observed = value & mask
    passed = bool(observed == exp)
    _emit(
        passed=passed,
        value=observed,
        exp=exp,
        alert_level=alert_level,
        msg=msg,
        scope=scope,
        msg_id=msg_id,
        radix=Radix.HEX,
        match=None,
    )
    return passed
```

Add it to `__init__.py` re-exports and write tests that cover the
WARNING / ERROR split (using the same accumulator reset trick in
`setUp`).

## Track more severities

`_TRACKED_LEVELS` controls what gets accumulated. Default is
`{TB_WARNING, WARNING}`. To also track `NOTE` (for example, when you
want every soft check to appear in reports):

```python
# in checks.py
_TRACKED_LEVELS = frozenset({
    AlertLevel.TB_WARNING,
    AlertLevel.WARNING,
    AlertLevel.NOTE,
    AlertLevel.INFO,
})
```

`SegDocument._generate()` and `report_test_summary()` automatically
pick up the new behaviour because they read the same accumulator.

## Add a custom report backend

`SegDocument._render_one()` is the only piece that touches `docxtpl`.
To swap it for, say, a Markdown or PDF renderer, subclass and override:

```python
# in docs.py
from hwval.docs import SegDocument
from hwval import TestSummary

class MarkdownSegDocument(SegDocument):
    def _render_one(self, template_path, output_path, context):
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader(template_path.parent))
        tpl = env.get_template(template_path.name)
        output_path.write_text(tpl.render(context))
        return output_path
```

You'll need to adjust the constructor's import guard (currently it
forces `docxtpl`).

## Capture logs into a structured sink

Add a `logging.Handler` subclass to the `hwval` logger:

```python
import logging
from hwval import set_logger

class JSONSink(logging.Handler):
    def emit(self, record):
        log_to_json_store({
            "level": record.levelname,
            "scope": ...,
            "msg_id": ...,
            "message": record.getMessage(),
        })

sink = JSONSink(level=logging.DEBUG)
logging.getLogger("hwval").addHandler(sink)
set_logger(logging.getLogger("hwval"))
```

Or replace the logger entirely via `set_logger(my_logger)`.

## Add a stub→real implementation

`check_stable`, `await_change`, `await_value`, `check_sb_completion`
raise `NotImplementedError` because they require VHDL simulation time
(or a UVVM scoreboard). On [cocotb](https://www.cocotb.org/) you can
implement them as wrappers around `cocotb.triggers` and re-export from
`hwval.cocotb` so users opt in explicitly.

## Add a CLI entry point

`hwval` is a library, not a CLI tool. If you want a thin CLI:

```python
# in src/hwval/__main__.py
import sys
from hwval import report_test_summary

if __name__ == "__main__":
    s = report_test_summary()
    sys.exit(0 if s.ok else 1)
```

Run as `python -m hwval` after running checks. The exit code is suitable
for CI integration.

## Derive `test_id` from your own scheme

The default `test_id` is a sequential `TID_<seq:04d>`. Install a
custom function to encode whatever makes sense in your project
(scope + msg_id, a hash, a counter, a timestamp prefix, …):

```python
from hwval import set_test_id_function

def make_test_id(record, seq):
    return f"{record.scope}.{record.msg_id}.{seq:04d}"

set_test_id_function(make_test_id)
```

The function receives the record *before* its `test_id` is filled in
(field is `""`) plus a 1-indexed counter that resets on
`reset_test_summary()`. When you swap the function, every record
already in the accumulator is re-stamped with the new function (each
record keeps its 1-indexed position) so the whole accumulator stays
consistent with whichever function is active. A buggy function never
breaks a check: the failure is caught, a DEBUG log line is emitted,
and the default function takes over for that one record.

If the function lives in a project module and you want to wire it
without touching Python, point the YML config at it via the standard
`"package.module:attr"` convention:

```yaml
# hwval.yml
test_id_function: "my_pkg.test_id_helpers:make_test_id"
```

```python
from hwval import SegDocument

doc = SegDocument(
    test_template="templates/test_performed.docx",
    results_template="templates/test_results.docx",
    config="hwval.yml",
)
```

`SegDocument(..., config=...)` is the only piece that needs the
optional `[docs]` extra (it pulls in PyYAML alongside docxtpl).

## Scope a field to one report; default missing fields to `""`

Each YML / `fields=` entry can be a plain string (the field
appears in *both* rendered reports) or a mapping that scopes it
to a subset:

```yaml
fields:
  - test_id                                    # both reports
  - name: msg_id
    reports: test_performed                    # only test_performed
  - name: msg
    reports: test_results                      # only test_results
  - operator                                   # both reports
```

The same shape works directly in Python via
:class:`hwval.docs.FieldSpec`:

```python
from hwval.docs import SegDocument

doc = SegDocument(
    test_template=...,
    results_template=...,
    fields=[
        "test_id",
        {"name": "msg_id", "reports": "test_performed"},
        {"name": "msg",    "reports": "test_results"},
    ],
)
```

A field declared in the YML/``fields=`` but not supplied to a
particular :func:`hwval.check_value` / :func:`hwval.check_value_in_range`
call shows up as the empty string in that row. To populate it,
pass the field name as a keyword argument to `check_value`:

```python
check_value(
    0xDEAD, 0xDEAD,
    alert_level=AlertLevel.WARNING,
    msg="REG0 OK", scope="reg_walk", msg_id="ID_REG0",
    operator="alice",         # → extras["operator"]
    retries=3,                # → extras["retries"]
)
```

`scope`, `msg`, `msg_id`, `radix`, `match_strictness`,
`alert_level` are reserved (named parameters of `check_value`);
everything else lands in :attr:`CheckRecord.extras`. Extras that
are not declared in the YML are silently dropped from the report
(still on the record, just not rendered).

## Gotchas to remember

- The `_summary_records` accumulator is **module-level**, not per-call.
  Always `reset_test_summary()` between unrelated test runs to avoid
  leakage.
- `SegDocument._generate(summary=None)` reads the accumulator via
  `current_summary()` without resetting — repeated calls produce the
  same output until you call `reset_test_summary()` or pass
  `report_test_summary(reset=True)`.
- `_emit()` raises *after* logging, so the log record is emitted even
  when the call raises. Capture with a handler to assert on log content
  without losing it to the raise.
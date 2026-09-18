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
# 03 · Severity levels

Demonstrates how `alert_level=` controls whether a check raises
`AssertionError`, only logs, or returns the boolean result.

## Run

```bash
uv run python examples/03_severity_levels/example.py
```

## What you'll see

Each demo prints a header line followed by a log record emitted by the
`hwval` logger (because this example configures the root logger), then the
post-call summary line.

```
[hard-mismatch] ERROR (1 vs 2)
ERROR hwval: [C_TB_SCOPE_DEFAULT] ID_POS_ACK FAIL: hard-mismatch   value=1 expected=2  match=MATCH_STD
  -> raised AssertionError: ...
```

## What it shows

| Severity              | On FAIL                                     |
| --------------------- | ------------------------------------------- |
| `TB_FAILURE`, `FAILURE` | log CRITICAL + raise `AssertionError`    |
| `TB_ERROR`, `ERROR`     | log ERROR     + raise `AssertionError`    |
| `TB_WARNING`, `WARNING` | log WARNING   (no raise)                  |
| `NOTE`, `INFO`          | log INFO      (no raise)                  |
| `DEBUG`, `LOGICAL`      | log DEBUG     (no raise)                  |

`WARNING`-class outcomes are also accumulated in module state — see
[06_report_test_summary](../06_report_test_summary).
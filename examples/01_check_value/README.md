# 01 · `check_value` basics

Demonstrates the core equality check: pass / fail, raise vs no-raise by
severity, sequence comparison, and tagging the log line with `scope`,
`msg_id`, `msg`, and `radix`.

## Run

```bash
uv run python examples/01_check_value/example.py
```

(From a plain virtualenv: `python examples/01_check_value/example.py`.)

## What you'll see

- All five `assert ... is True` lines run silently.
- Step 4 prints one `ERROR raised as expected: ...` line (the
  `AssertionError` caught manually).
- The final `print()` confirms the demo completed.

## What it shows

| Step | Demonstrates                                                       |
| ---: | ------------------------------------------------------------------ |
| 1    | `check_value(value, exp)` returns `True` on a passing check        |
| 2    | `scope=`, `msg_id=`, `msg=`, `radix=` for tagged log lines         |
| 3    | `WARNING` returns `False` instead of raising                       |
| 4    | Default `ERROR` severity raises `AssertionError` on failure        |
| 5    | Sequences (lists/tuples) compare element-wise                      |
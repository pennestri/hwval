# 02 · `check_value_in_range` basics

Inclusive range check: `min_value <= value <= max_value`. Identical
severity / log / raise semantics to `check_value`.

## Run

```bash
uv run python examples/02_check_value_in_range/example.py
```

## What you'll see

- All `assert` lines pass silently.
- Step 4 prints one `ERROR raised as expected: ...` line.
- Step 5 emits a log line at `WARNING` level (since the default for this
  check is `ERROR` and the sample is inside the band, no log line is
  printed to the console unless you attach a handler).
- The final `print()` confirms the demo completed.

## What it shows

| Step | Demonstrates                                                  |
| ---: | ------------------------------------------------------------- |
| 1    | Value inside the range returns `True`                        |
| 2    | Boundary values (`min` and `max`) are inclusive              |
| 3    | Out-of-range `WARNING` returns `False` (no raise)           |
| 4    | Out-of-range default `ERROR` raises `AssertionError`         |
| 5    | Realistic ADC-style range check with `scope`/`msg_id`       |
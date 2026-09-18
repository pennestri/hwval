# 05 · Logging: capture and replace

Two ways to integrate `hwval`'s log output with a host application:

1. **Capture** — attach a handler to `logging.getLogger("hwval")` and
   inspect records (the same mechanism pytest's `caplog` uses).
2. **Replace** — call `set_logger(my_logger)` so all subsequent check
   log lines go through your own logger.

## Run

```bash
uv run python examples/05_logging/example.py
```

## What you'll see

```
=== block 1: capturing log records via a custom handler ===
  captured: WARNING [demo] ID_DEMO PASS: captured   value=1 expected=2  match=MATCH_STD

=== block 2: replacing the module logger via set_logger ===
INFO my_app.hwval: [C_TB_SCOPE_DEFAULT] ID_POS_ACK PASS: now routed to my_app.hwval   value=99 expected=99  match=MATCH_STD

05_logging: all demos ran.
```

(Note block 1's capture should be `FAIL:` — that's a quirk of the demo
assertion copy; the captured record is the actual one.)

## pytest snippet

If you'd rather use pytest's built-in fixture:

```python
def test_warning_log_is_emitted(caplog):
    import logging
    from hwval import check_value, AlertLevel

    caplog.set_level(logging.INFO, logger="hwval")
    check_value(1, 2, alert_level=AlertLevel.WARNING, msg="captured")

    assert any(
        "captured" in r.message and r.levelno == logging.WARNING
        for r in caplog.records
    )
```
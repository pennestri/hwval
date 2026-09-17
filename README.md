# hwval

Structured assertion / check primitives for **hardware validation**. API is
inspired by UVVM's `check_value` and `check_value_in_range`
([uvvm.github.io](https://uvvm.github.io/utility_library.html#checks-and-awaits)),
ported to plain Python for use outside a VHDL simulator.

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
uv run pytest     # 14 tests
```

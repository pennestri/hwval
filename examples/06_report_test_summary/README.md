# 06 · `report_test_summary`

`WARNING` / `TB_WARNING` checks don't raise, so a single mismatch is silent.
`report_test_summary()` surfaces every WARNING check that ran — passing
and failing — and returns a structured `TestSummary`.

## Run

```bash
uv run python examples/06_report_test_summary/example.py
```

## What you'll see

```
Test Summary: 3 passed, 2 failed

FAILED (2):
  [reg_walk] ID_REG1 REG1 drift
      value=1 expected=2  match=MATCH_STD
  [C_TB_SCOPE_DEFAULT] ID_POS_ACK REG4 range
      value=500 expected=in [10, 100]

PASSED (3):
  [reg_walk] ID_REG0 REG0 OK
      value=0 expected=0  match=MATCH_STD
  ...

structured counts: passed=3 failed=2 ok=False
empty summary after reset: total=0
```

## What it shows

| Step | Demonstrates                                                   |
| ---: | -------------------------------------------------------------- |
| 1    | A mix of passing and failing WARNING checks accumulate         |
| 2    | ERROR-class checks are excluded from the summary              |
| 3    | `report_test_summary(file=...)` prints + returns a result    |
| 4    | `summary.passed_count`, `summary.failed_count`, `summary.ok`  |
| 5    | Default `reset=True` clears the accumulator after reporting   |

`TestSummary` and `CheckRecord` are exported dataclasses you can `import`
and use programmatically.

## Test-fixture tip

```python
import pytest
from hwval import reset_test_summary

@pytest.fixture(autouse=True)
def _clean_summary():
    reset_test_summary()
    yield
    reset_test_summary()
```
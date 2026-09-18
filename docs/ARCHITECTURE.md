# Architecture

`hwval` is intentionally small — a single core module plus one optional
submodule. Everything stays in the source tree under `src/hwval/`.

## Module layout

```
src/hwval/
├── __init__.py     # re-exports the public API; lazy-loads SegDocument
├── checks.py       # core: AlertLevel/MatchStrictness/Radix enums,
│                   #       check_value, check_value_in_range,
│                   #       accumulator + report_test_summary,
│                   #       current_summary, CheckRecord, TestSummary,
│                   #       _emit(), set_logger
└── docs.py         # optional: SegDocument class (lazy-imports docxtpl)
```

### `checks.py`

Owns:

- The enums (`AlertLevel`, `MatchStrictness`, `Radix`).
- The module-level logger (`logging.getLogger("hwval")`).
- The two severity tables:
  - `_ALERT_TO_LEVEL` — maps `AlertLevel` → stdlib logging level.
  - `_RAISING_LEVELS` — set of severities that raise `AssertionError`.
  - `_TRACKED_LEVELS` — set of severities accumulated for
    `report_test_summary` / `SegDocument`.
- The accumulator: `_summary_records: list[CheckRecord]`.
- The shared `_emit()` helper that both public check functions call.
- Public entry points: `check_value`, `check_value_in_range`,
  `set_logger`, `report_test_summary`, `reset_test_summary`,
  `current_summary`.

### `docs.py`

Owns:

- `SegDocument` class — binds two `.docx` templates + reporting options,
  renders them via `docxtpl` in `_generate()`.
- Two private dataclasses / helpers (`_TemplateContext`, `_record_to_dict`,
  `_select`).

The `docxtpl` import is **lazy** (inside the constructor and the
`_render_one` helper) so users who never touch `SegDocument` don't pay
the dependency cost.

### `__init__.py`

Two-phase. The core symbols are imported eagerly. `SegDocument` is
imported inside a `try/except ImportError` so the package still loads
without the `[docs]` extra.

## Data flow

```
                    ┌────────────────────┐
   caller ───────►  │  check_value(…)    │
                    │  check_value_in_   │──►  _emit()
                    │     range(…)       │         │
                    └────────────────────┘         │
                                                   ▼
                          ┌──────────────────────────────┐
                          │ _emit() (shared)             │
                          ├──────────────────────────────┤
                          │ • log at mapped stdlib level │
                          │ • append to _summary_records │
                          │   iff level ∈ _TRACKED_LEVELS│
                          │ • raise if FAIL + level ∈    │
                          │   _RAISING_LEVELS            │
                          └──────────────────────────────┘
                                          │
                                          ▼
                          ┌──────────────────────────────┐
                          │ Accumulator consumers        │
                          ├──────────────────────────────┤
                          │ • report_test_summary()      │
                          │ • current_summary()          │
                          │ • SegDocument._generate()    │
                          └──────────────────────────────┘
```

## Extension points

| Want to...                              | Add / change                                |
| --------------------------------------- | ------------------------------------------- |
| Track more severity levels              | extend `_TRACKED_LEVELS` in `checks.py`     |
| Change raise-on-fail behaviour          | tweak `_RAISING_LEVELS`                     |
| Add a third check primitive             | new public function in `checks.py` calling `_emit()` |
| Switch the report docx engine           | replace `docxtpl` in `docs.py:_render_one`  |
| Capture / reroute log records           | add a handler to the `hwval` logger or call `set_logger()` |

See [`EXTENDING.md`](./EXTENDING.md) for worked examples.

## Why a single shared `_emit()`?

Both `check_value` and `check_value_in_range` need to:

1. Compute pass/fail.
2. Format the value/expected line.
3. Emit a log record.
4. Maybe append to the accumulator.
5. Maybe raise.

Centralising this in `_emit()` means a new check primitive only needs to
compute `passed` and the rendered `value`/`exp` strings — it doesn't have
to re-implement log + record + raise.

## Dependency policy

The base library has **zero required dependencies**. The `[docs]` extra
adds `docxtpl` (which transitively pulls in `python-docx` and `jinja2`)
for `SegDocument`. Anything heavier needs explicit user opt-in.
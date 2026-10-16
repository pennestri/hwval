# Examples

Each subfolder focuses on one feature of `hwval`. Run them with
`uv run python examples/NN_xxx/example.py` (or `python ...` from any
virtualenv where `hwval` is installed).

| #   | Folder                                              | Demonstrates                                                       |
| --- | --------------------------------------------------- | ------------------------------------------------------------------ |
| 01  | [01_check_value](./01_check_value)                 | `check_value` — pass/fail, raise, sequence, tagging                 |
| 02  | [02_check_value_in_range](./02_check_value_in_range) | `check_value_in_range` — inclusive bounds, severity behaviour       |
| 03  | [03_severity_levels](./03_severity_levels)          | All `AlertLevel` values — ERROR raises, WARNING logs only           |
| 04  | [04_radix_and_tags](./04_radix_and_tags)            | `radix`, `scope`, `msg_id`, `msg`, positional `MatchStrictness`    |
| 05  | [05_logging](./05_logging)                          | Capture log records; replace the module logger via `set_logger`     |
| 06  | [06_report_test_summary](./06_report_test_summary)  | `report_test_summary`, `reset_test_summary`, `TestSummary`          |
| 07  | [07_seg_document](./07_seg_document)                | `SegDocument._generate` — two `.docx` reports from Jinja2 templates |
| 08  | [08_test_id_and_yaml](./08_test_id_and_yaml)        | `test_id` field + user-supplied update fn + YML config for `SegDocument` |

## Run them all

```bash
for d in examples/0?_*/; do
  echo "=== $d ==="
  uv run python "$d/example.py" || echo "  -> failed"
done
```

## Install

The base library is dependency-free. Examples 07 and 08 need the
optional `docs` extra (`docxtpl` + `python-docx` + `jinja2` +
`pyyaml`):

```bash
uv add hwval[docs]
```

## Learning path

1. **Start with 01–04** to understand the building blocks.
2. **Move to 05** to see how logs flow through stdlib logging.
3. **Then 06** to learn about the WARNING summary — the foundation for
   `SegDocument`.
4. **Finish with 07** for the end-to-end docx report workflow.
5. **Wrap up with 08** to see `test_id` plus the YAML-driven report
   config.
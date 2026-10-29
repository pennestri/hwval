# Changelog

All notable changes to `hwval` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [SemVer](https://semver.org/).

## [0.1.0] — Unreleased

First alpha. Structured check primitives for hardware validation, with a
severity model, radix-aware logging, and docx test reports.

### Added

- `check_value` / `check_value_in_range` — the checks. Severity via
  `AlertLevel`, display radix via `Radix`, tags via `scope` / `msg_id` /
  `msg`, comparison mode via `MatchStrictness`.
- `AlertLevel`, `MatchStrictness`, `Radix` — the enums above.
- `CheckRecord` — the structured record of one check (scope, msg_id,
  value, expected, radix, `test_id`, `seq`).
- `current_summary`, `report_test_summary`, `reset_test_summary` —
  accumulate the checks of a run into a `TestSummary`.
- `set_logger` — route the library's log records to your own logger.
- `set_test_id_function` / `get_test_id_function` — per-check identifiers.
- `format_value` — radix-aware value formatting.
- `SegDocument`, `FieldSpec` — render two docx reports (`test_performed`,
  `test_results`) from Jinja2/docxtpl templates, with per-field scoping.
- `load_seg_config` — read the `hwval.yml` configuration
  (`fields`, `include_passed`, `include_failed`, `test_id_function`).
- Two GUIs for the YML config: `tools/seg_config_gui/` (static HTML) and
  `tools/seg_config_gui_flask/` (Flask; also loads an existing YML back
  into the form).
- Eight runnable examples under `examples/`.

### Changed

- The `test_performed` report is chronological: `CheckRecord.seq` carries
  the sequence number of the check and the report is sorted by it, so it
  reads like a log of what ran. The `test_results` report stays grouped
  by passed / failed.
- SEG documents honour the radix of the check that produced each record,
  so a record logged as hex prints as hex in the report.
- The GUI no longer lets the user rename the default fields, and shows
  the default field by default.

# 08 · `test_id` field + YML-driven `SegDocument` config

Two new pieces of `hwval` that work together nicely:

1. **A `test_id` field on every WARNING-level `CheckRecord`.** The id
   comes from a user-supplied *update function* that sees the record
   and a 1-indexed sequence counter. The default emits a sequential
   `TID_<seq:04d>`; install your own with `set_test_id_function(...)`.
2. **A YAML config file for `SegDocument`.** The fields the report
   exposes, the include toggles, and the test-id update function can
   all live in a `hwval.yml` next to the test code. Edit the YAML,
   re-run, the report layout updates — no Python change required.

The YML loader takes the same keys the `SegDocument` constructor does
(`fields`, `include_passed`, `include_failed`, `test_id_function`).
Explicit constructor arguments always win over the YAML, so you can
override on a per-call basis.

## Requirements

```bash
uv add hwval[docs]
# or
pip install hwval[docs]
```

`hwval[docs]` pulls in `docxtpl`, `python-docx`, `jinja2`, **and
`pyyaml`** for the YAML config loader.

## Run

```bash
uv run python examples/08_test_id_and_yaml/example.py
```

## Files

```
examples/08_test_id_and_yaml/
├── README.md
├── example.py           # generates templates, runs checks, renders docs
├── hwval.yml            # drives the SegDocument config
├── test_id_helpers.py   # the user-supplied test_id update function
└── out/                 # rendered .docx files end up here
```

## What it shows

| Step | Demonstrates                                                          |
| ---: | --------------------------------------------------------------------- |
| 1    | A user-supplied `test_id` function in `test_id_helpers.py`           |
| 2    | Driving the same knobs (fields, toggles, id function) from `hwval.yml` |
| 3    | Loading the YAML via `SegDocument(..., config="hwval.yml")`           |
| 4    | The `test_id` field appearing in the rendered docx alongside the others |

## YAML format

```yaml
# hwval.yml
fields:
  - test_id
  - msg
  - scope
  - msg_id
  - passed
  - detail
include_passed: true
include_failed: true
test_id_function: "examples.test_id_helpers:make_test_id"
```

- `fields` is the list of `CheckRecord` attribute names exposed to the
  Jinja templates. Anything not listed is invisible inside the
  template.
- `include_passed` / `include_failed` toggle the two record buckets
  the docx reports emit.
- `test_id_function` is a `"package.module:attr"` reference (same
  convention as `logging.config.dictConfig` and `pickle`) to a
  function with signature `(record, sequence) -> str`.

Any unknown key in the YAML is a hard error so typos surface early
instead of being silently ignored.

## test_id function shape

```python
def make_test_id(record, seq):
    return f"{record.scope}.{record.msg_id}.{seq:04d}"
```

The function sees the `CheckRecord` *before* `test_id` is filled in
(field is `""`) plus a 1-indexed counter that resets on
`reset_test_summary()`. It returns the new id as a string. Anything
the function can compute — hash, counter, scope+msg combo, time
prefix, … — is fair game.

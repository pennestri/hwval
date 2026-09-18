# hwval — project documentation

This folder holds **project-level** documentation: the developer / user
guide. For the public Python API, see [`README.md`](../README.md) at the
repo root. For runnable, feature-by-feature examples, see
[`examples/`](../examples).

## Contents

| File                                                 | Audience          | Purpose                                                |
| ---------------------------------------------------- | ----------------- | ------------------------------------------------------ |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md)               | contributors      | Module layout, data flow, extension points             |
| [`PUBLIC_API.md`](./PUBLIC_API.md)                   | users             | Full reference for every public symbol                 |
| [`EXTENDING.md`](./EXTENDING.md)                     | contributors      | Adding new check primitives, log targets, doc renderers |
| [`RELEASE.md`](./RELEASE.md)                         | maintainers       | Versioning, packaging, release checklist                |
| [`generated/`](./generated)                          | humans / auditors | Pre-rendered `.docx` test reports (see below)          |

## Generated test reports

[`generated/generate.py`](./generated/generate.py) uses `SegDocument` to
render two `.docx` files describing what tests were performed against
the project itself and what their results were. Re-run it any time:

```bash
uv run python docs/generated/generate.py
```

Outputs:

- `generated/hwval_test_performed.docx` — what was tested.
- `generated/hwval_test_results.docx`  — outcomes (counts + per-record
  detail).

These files are not committed in the repo by default (they're regenerated
on demand); commit them when you want a snapshot attached to a release.

## Where to start

- New user of `hwval` → [`../README.md`](../README.md), then [`../examples`](../examples).
- Contributing a change → [`ARCHITECTURE.md`](./ARCHITECTURE.md), then
  [`EXTENDING.md`](./EXTENDING.md).
- Cutting a release → [`RELEASE.md`](./RELEASE.md).
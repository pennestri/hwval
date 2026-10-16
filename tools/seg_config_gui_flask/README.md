# SegDocument YML Config Generator · Flask

A pure-Python Flask app for building a `hwval.yml` for
`SegDocument`. The YML generation, validation and download run on
the server, so the browser is a thin client: vanilla HTML form
plus a few lines of vanilla JS for add / remove / drag-reorder.

The validation logic uses the same `hwval.docs.FieldSpec` and
`hwval.docs.load_seg_config` code the real `SegDocument`
constructor uses, so a green "ready to download" badge means the
YML will load without error.

## Install + run

The dev `flask` dep is already declared in `pyproject.toml`:

```bash
uv sync --extra docs
uv run python tools/seg_config_gui_flask/app.py
```

…then open <http://127.0.0.1:5000/> in a browser. The dev server
binds to localhost only; edit `app.run(host=...)` in
[`app.py`](app.py) to expose it on the LAN.

## Endpoints

| Route             | Methods | What it does                                          |
| ----------------- | ------- | ----------------------------------------------------- |
| `GET /`           | GET     | Render the empty form with the demo fields.            |
| `POST /`          | POST    | Validate the form and re-render with the generated YML, Python-kwargs preview, and a "Download hwval.yml" button. |
| `POST /download`  | POST    | Same validation, but the response is `Content-Disposition: attachment; filename=hwval.yml` so the browser saves the file directly. |
| `GET /healthz`    | GET     | Cheap `{"status": "ok"}` liveness probe.               |

## UI

Three steps, then a "Generated YML" panel once a POST succeeds:

1. **Fields** — one row per field. Edit the name, pick a report
   scope, drag the handle to reorder, click *Delete* to remove, or
   *Insert preset* to add a built-in `CheckRecord` field or a
   common user extra with one click.
2. **Settings** — toggles for `include_passed` / `include_failed`
   and the optional `test_id_function` (`"package.module:attr"`
   form).
3. **Generate** — submits the form. Server validates, re-renders
   with the YML + Python-kwargs preview.
4. **Download hwval.yml** — POSTs the same field/settings state
   to `/download` and saves the response as a file.

Validation errors stay on the same page, attached to the top of
the form, with a one-line description per error.

## Validation rules

All of these are enforced server-side. A failure turns the
output panel into an error list; the form is preserved so the
user can fix and re-submit.

* at least one field must have a name
* each field name must be a valid Python identifier
  (`^[A-Za-z_][A-Za-z0-9_]*$`)
* field names must be unique
* `reports` must be one of `all`, `test_performed`, `test_results`
* if `test_id_function` is set, it must be of the form
  `"package.module:attr"` (a single colon, both halves non-empty)

Defence in depth: after the form-level checks pass, the server
writes the YML to a temp file and runs it through the real
`hwval.docs.load_seg_config` loader. If the loader rejects the
YML the form is re-rendered with an error (e.g. a future stricter
loader upgrade is caught immediately).

## What it generates

```yaml
fields:
  - test_id                                    # plain string: in both reports
  - name: msg_id                               # dict: scoped to a single report
    reports: test_performed
  - name: msg
    reports: test_results
  - name: detail
    reports: test_results
  - value
  - expected
  - passed
  - operator

include_passed: true
include_failed: true
test_id_function: "package.module:make_test_id"   # only if set
```

That file is then loaded by:

```python
from hwval import SegDocument

doc = SegDocument(
    test_template="templates/test_performed.docx",
    results_template="templates/test_results.docx",
    config="hwval.yml",
)
```

## Smoke test (no browser)

```bash
uv run python tools/seg_config_gui_flask/app.py &
PID=$!
sleep 1

# Form-rendered YML
curl -s -X POST http://127.0.0.1:5000/ \
  --data-urlencode "field_name=test_id" \
  --data-urlencode "field_reports=all" \
  --data-urlencode "field_name=msg" \
  --data-urlencode "field_reports=test_results" \
  --data-urlencode "include_passed=on" \
  --data-urlencode "include_failed=on" \
  | grep -A 6 "<pre"

# Direct file download
curl -s -X POST http://127.0.0.1:5000/download \
  --data-urlencode "field_name=test_id" --data-urlencode "field_reports=all" \
  --data-urlencode "include_passed=on" --data-urlencode "include_failed=on" \
  -o hwval.yml

kill $PID
```

## Files

```
tools/seg_config_gui_flask/
├── README.md
├── app.py
└── templates/
    ├── base.html
    └── index.html
```

`app.py` is the only Python file; the two templates are plain
Jinja2 / HTML / vanilla CSS (no JS framework, no CDN).

## Comparison with `tools/seg_config_gui/`

The static HTML/JS form in [`tools/seg_config_gui/`](../seg_config_gui/)
has zero dependencies and runs entirely in the browser — useful
when you want to drop the file on a USB stick or share it with
someone who can't / won't install Python. This Flask version
moves the YML generation onto the server, so the validation
matches the real Python loader exactly, multi-user edits are
possible (each request is independent), and the same Flask app
can be deployed somewhere central for a team to share.

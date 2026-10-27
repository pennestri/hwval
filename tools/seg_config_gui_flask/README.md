# SegDocument YML Config Generator · Flask

A pure-Python Flask app for building a `hwval.yml` for
`SegDocument`. The YML generation, validation and download run on
the server, so the browser is a thin client: vanilla HTML form
plus a few lines of vanilla JS for add / remove / drag-reorder.

The app also generates the two starter `.docx` templates that
`SegDocument` consumes (`test_performed.docx` +
`test_results.docx`), pre-filled with the fields you declared and
a placeholder for every extra-context key.

An existing `hwval.yml` can be uploaded to fill the form in again,
so an existing config never has to be retyped by hand.

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
| `POST /`          | POST    | Validate the form and re-render with the generated YML, Python-kwargs preview, and the download buttons. |
| `POST /download`  | POST    | Same validation, but the response is `Content-Disposition: attachment; filename=hwval.yml` so the browser saves the file directly. |
| `POST /download-template/<report>` | POST | Same validation, but the response is the starter `.docx` template for `<report>` (`test_performed` or `test_results`). |
| `POST /load`      | POST    | Upload an existing `hwval.yml` (multipart) and re-render the form filled in with it. |
| `GET /healthz`    | GET     | Cheap `{"status": "ok"}` liveness probe.               |

`<report>` must be `test_performed` or `test_results`; anything
else is a 404.

## Load an existing config

The *Load an existing config* card at the top of the page takes a
`.yml` file upload. The file is validated with the real
`hwval.docs.load_seg_config` loader — the same code the generated
YML is checked against — and the form is then filled in with:

* the `fields` list, in file order, with the per-report scope
  preserved (a field scoped to `test_performed` stays scoped to
  `test_performed`);
* the `include_passed` / `include_failed` toggles;
* the `test_id_function` dotted path.

A file the loader rejects is reported with the loader's own message
(plus the file name instead of the temp path the loader read):

```
Could not load the config:
  - unknown SegDocument config key(s) in hwval.yml: ['bogus_key']; …
```

The extra context is not part of the YML, so the rows you already
typed are carried over the load untouched.

## UI

Five steps, then a "Generated YML" panel once a POST succeeds:

1. **Fields** — one row per field. Edit the name, pick a report
   scope, drag the handle to reorder, click *Delete* to remove, or
   *Insert preset* to add a built-in `CheckRecord` field or a
   common user extra with one click. Every known field name shows a
   one-line explanation under the input, and the *What do the fields
   mean?* panel documents them all (see *Field reference* below).
   The name of a **preset field is locked** (see *Preset field names
   are fixed* below).
2. **Settings** — toggles for `include_passed` / `include_failed`
   and the optional `test_id_function` (`"package.module:attr"`
   form).
3. **Extra context** — key/value pairs that become variables in the
   templates (`{{ project }}`) and are merged into the Jinja context
   by `SegDocument(extra_context=...)`.
4. **Generate** — submits the form. Server validates, re-renders
   with the YML + Python-kwargs preview.
5. **Generated YML** — the YML text plus the equivalent Python
   kwargs.

The download buttons become active once the form validates:

* **Download hwval.yml** — the YML config file.
* **Download test_performed.docx** / **Download
  test_results.docx** — the two starter templates.

Validation errors stay on the same page, attached to the top of
the form, with a one-line description per error.

## Preset field names are fixed

The names offered by the *Insert preset* dropdown are **locked**: the
name input of such a field is read-only, marked with a `preset` badge,
and explained on hover.

```
test_id    [the observed value…      ] preset
```

Why: the value of a field is read *by name*. The built-in attributes
come from the record itself (`CheckRecord.test_id`, `.value`,
`.passed`, …) and the user extras come from the keyword argument you
passed to the check (`operator="alice"`). Rename `test_id` to `tid`
and the report column is simply empty — the value is still looked up
under the old name.

What you can still do with a preset field:

* change its **report scope** (e.g. show `msg` only in `test_results`);
* **reorder** it;
* **delete** it.

What stays editable:

* the **name of a custom field** — any name that is not a preset;
* the report scope of every field.

Typing a preset name into a custom field locks it too, so the name a
preset field is known by stays consistent everywhere.

> The lock is a `readonly` attribute — the value is still submitted
> with the form, so a preset field never silently disappears from the
> generated YML. (A `disabled` attribute would drop it.)

## Field reference

The Fields card documents the fields it knows about, in two places.

**Under each field name** — a one-liner that appears as soon as the
name matches a known field (and disappears when it does not):

| Field | Hint shown under the input |
| ----- | --------------------------- |
| `test_id` | id of the test, from the test_id function |
| `scope` | grouping tag of the check |
| `msg_id` | id of the check |
| `msg` | message of the check |
| `value` | the observed value |
| `expected` | the value it was compared against |
| `passed` | did the check pass? |
| `detail` | one-line detail of the comparison |
| `operator` | user extra — set by `operator=` on the check |
| `notes`, `address`, `retries`, `seq_id` | user extra — set by `<name>=` on the check |

**In the *What do the fields mean?* panel** — the full table: what
each field holds, where its value comes from, and a `pre-filled`
badge on the fields the GUI starts with.

The wording follows the `CheckRecord` docstring in `hwval.checks` —
the authoritative description of what each attribute holds.

### Where a field's value comes from

For every field the template looks, in order:

1. your **extras** — any keyword argument you passed to
   `check_value` / `check_value_in_range`;
2. the built-in attribute of the same name;
3. the empty string.

So a field you declare but never pass renders as an empty cell, and a
field named after a built-in is filled from the built-in unless you
also pass it as an extra.

## Extra context

`extra_context` is the mapping `SegDocument` merges into the Jinja
context of both reports. Every key you declare:

* shows up as a `{{ <key> }}` placeholder in the header of both
  downloaded `.docx` templates (labelled with a humanised version
  of the key, e.g. `dut_serial` → `Dut Serial:`);
* shows up in the *Python kwargs* preview as
  `extra_context={"project": "Acme DUT v3", ...}`.

Values are typed in as text and coerced to a Python scalar when
they are unambiguous: `true` / `false` → `bool`, `null` / `none` →
`None`, integers and floats → numbers, everything else stays a
string.

`extra_context` is deliberately **not** written into `hwval.yml`:
`hwval.docs.load_seg_config` only accepts `fields`,
`include_passed`, `include_failed` and `test_id_function`, so an
unknown key would make the loader reject the file. Pass the
mapping to the constructor instead:

```python
doc = SegDocument(
    test_template="templates/test_performed.docx",
    results_template="templates/test_results.docx",
    config="hwval.yml",
    extra_context={"project": "Acme DUT v3", "operator": "alice"},
)
```

## The generated `.docx` templates

Each download produces a Word document that is a valid docxtpl
template:

* a heading (`Test Performed` / `Test Results`);
* a header line with every extra-context key, the record counts and
  `{{ generated_at }}`;
* one table per section, whose header row holds the field names you
  declared **for that report** and whose data row holds one
  `{{ rec.<field> }}` placeholder per field.

The loop is expressed with docxtpl's row tag:

```
{%tr for rec in failed %}     ← row removed by docxtpl
{{ rec.test_id }}             ← row repeated once per record
{%tr endfor %}                ← row removed by docxtpl
```

`test_performed.docx` loops over `records`; `test_results.docx` has
a *Failed tests* table (looping over `failed`) and a *Passed tests*
table (looping over `passed`).

Open the files in Word, adjust the layout and **keep the
placeholders and the `{%tr %}` tags** — docxtpl needs them to
render the records. If a report has no fields at all, the template
says so instead of emitting an empty table.

## Validation rules

All of these are enforced server-side. A failure turns the
output panel into an error list; the form is preserved so the
user can fix and re-submit.

* at least one field must have a name
* each field name must be a valid Python identifier
  (`^[A-Za-z_][A-Za-z0-9_]*$`)
* field names must be unique
* `reports` must be one of `all`, `test_performed`, `test_results`
* each extra-context key must be a valid Python identifier and must
  not be a Python keyword
* extra-context keys must be unique
* extra-context keys must not shadow a built-in template variable
  (`summary`, `passed`, `failed`, `records`, `fields`,
  `include_passed`, `include_failed`, `generated_at`) or a Jinja
  literal (`true`, `false`, `none`)
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

# Starter .docx templates (fields + extra context)
curl -s -X POST http://127.0.0.1:5000/download-template/test_results \
  --data-urlencode "field_name=test_id" --data-urlencode "field_reports=all" \
  --data-urlencode "field_name=msg" --data-urlencode "field_reports=test_results" \
  --data-urlencode "ctx_key=project" --data-urlencode "ctx_value=Acme DUT v3" \
  -o test_results.docx

# Load an existing .yml back into the form
curl -s -X POST http://127.0.0.1:5000/load -F "yml_file=@hwval.yml" \
  | grep -E "Loaded|field_name"

# Check what landed in the template
uv run python - <<'PY'
from docx import Document
doc = Document("test_results.docx")
print([p.text for p in doc.paragraphs if p.text.strip()])
for t in doc.tables:
    for row in t.rows:
        print([c.text for c in row.cells])
PY

kill $PID
```

## Files

```
tools/seg_config_gui_flask/
├── README.md
├── app.py
├── docx_templates.py
└── templates/
    ├── base.html
    └── index.html
```

`app.py` holds the Flask routes and the form ↔ YML logic;
`docx_templates.py` builds the starter `.docx` templates (it only
needs `python-docx`, imported lazily). The two HTML files are plain
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

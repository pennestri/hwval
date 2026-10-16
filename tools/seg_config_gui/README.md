# SegDocument YML Config Generator

A self-contained HTML/JS form for building a `hwval.yml` for
`SegDocument` without hand-editing YAML. Open the file in a browser,
click fields and toggles, copy or download the resulting YAML.

## Open it

The file is a single self-contained HTML document with no
dependencies (no CDN, no build step, no server). Open it directly:

```bash
xdg-open tools/seg_config_gui/index.html    # Linux
open tools/seg_config_gui/index.html        # macOS
start tools/seg_config_gui/index.html       # Windows
```

…or drag the file into a browser tab. The page is plain HTML+JS; it
runs entirely in the browser, makes no network calls, and stores
nothing.

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

## UI tour

| Section        | What it does                                          |
| -------------- | ----------------------------------------------------- |
| **Fields**     | A row per field. Edit name, pick a report scope, drag to reorder, delete, or add new. The "preset" dropdown inserts a built-in `CheckRecord` field or a common extra with one click. |
| **Settings**   | Toggles for `include_passed` / `include_failed`, and an optional `test_id_function` (`"package.module:attr"` form). |
| **Generated YML** | Live preview. Validation status appears at the top of the section. **Copy to Clipboard** puts the YAML on the clipboard. **Download hwval.yml** saves it as a file. **Reset to defaults** wipes everything back to the demo fields. |
| **Python kwargs** *(expandable)* | Shows the equivalent `SegDocument(..., fields=[...], ...)` Python call you would write if you skipped the YAML. |

## Validation

The status chip at the top of the YML output flips red on:

* empty field names
* names that are not valid Python identifiers
* duplicate field names
* invalid `reports` values
* a `test_id_function` that does not match `"package.module:attr"`

Validation runs on every keystroke; fix the issue and the chip
flips back to green.

## Privacy

The page does not send anything over the network. It does not
require a server. The clipboard write uses the browser's
`navigator.clipboard` API (HTTPS / `localhost` only); the
**Copy to Clipboard** button falls back to a `document.execCommand`
shim on plain HTTP.

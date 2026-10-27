"""Flask web app for building a ``hwval`` SegDocument YML config.

A pure-Python alternative to the static HTML GUI in
``tools/seg_config_gui/``. The YML generation and validation run on
the server, using the same ``hwval.docs.FieldSpec`` and
``hwval.docs.load_seg_config`` code path the real ``SegDocument``
constructor uses — so a "valid" form submission produces a YML
file that will load without error.

Run with::

    uv run python tools/seg_config_gui_flask/app.py

…then open http://localhost:5000/ in a browser. The form lets you
add, remove and reorder fields, pick a per-report scope for each
field, set the include toggles and an optional test_id_function,
declare an ``extra_context`` mapping, and see the generated YML on
the same page. A "Download hwval.yml" button saves the YML as a
file; an expandable "Python kwargs" panel shows the equivalent
``SegDocument(..., fields=[...])`` call.

The app also generates the two starter ``.docx`` templates
(``test_performed.docx`` / ``test_results.docx``) that
:class:`hwval.docs.SegDocument` consumes. Each template holds the
fields the user declared — scoped to that report — as table columns
plus a ``{{ rec.<field> }}`` placeholder per field, and exposes every
``extra_context`` key as a ``{{ <key> }}`` placeholder.

An existing ``hwval.yml`` can be uploaded (``POST /load``) to fill
the form in again; the upload is validated with the real
:func:`hwval.docs.load_seg_config` loader, so the form only ever
shows a config that loads at runtime.

Requires the ``flask`` dev dependency (``uv sync`` pulls it in) and
the ``hwval`` package on the Python path. The ``.docx`` download
additionally needs the optional ``[docs]`` extra (python-docx).
"""

from __future__ import annotations

import keyword
import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

import yaml
from flask import (
    Flask,
    Response,
    render_template,
    request,
    send_file,
)

try:  # pragma: no cover - import shim
    import docx_templates
except ImportError:  # pragma: no cover - direct-script import fallback
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import docx_templates

from hwval.docs import FieldSpec, load_seg_config

# The MIME type Word documents are served with.
DOCX_MIMETYPE = (
    "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.document"
)


# --------------------------------------------------------------------------- #
# App factory                                                                #
# --------------------------------------------------------------------------- #


def create_app() -> Flask:
    """Build and return a configured Flask app.

    Exposed as a factory so tests / a custom runner can spin up an
    app without going through ``app.run()``.
    """
    app = Flask(__name__)
    # 8 MB request limit is plenty for a form with a few hundred
    # fields. The default 500 KB is also fine for the typical case
    # but this leaves headroom for the "paste a YML and edit it"
    # feature.
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

    app.add_url_rule("/", view_func=index, methods=["GET", "POST"])
    app.add_url_rule("/download", view_func=download, methods=["POST"])
    app.add_url_rule(
        "/download-template/<report>",
        view_func=download_template,
        methods=["POST"],
    )
    app.add_url_rule("/load", view_func=load_config, methods=["POST"])
    app.add_url_rule("/healthz", view_func=healthz, methods=["GET"])

    return app


# Default fields shown on the first GET (also used to repopulate the
# form when a POST comes in with an empty fields list).
DEFAULT_FIELDS: list[dict[str, str]] = [
    {"name": "test_id",  "reports": "all"},
    {"name": "msg_id",   "reports": "test_performed"},
    {"name": "msg",      "reports": "test_results"},
    {"name": "detail",   "reports": "test_results"},
    {"name": "value",    "reports": "all"},
    {"name": "expected", "reports": "all"},
    {"name": "passed",   "reports": "all"},
    {"name": "operator", "reports": "all"},
]

REPORT_OPTIONS: list[tuple[str, str]] = [
    ("all",            "both reports"),
    ("test_performed", "test_performed only"),
    ("test_results",   "test_results only"),
]

# A small library of preset names the user can pick from the "Insert
# preset" dropdown. Mirrors the static HTML GUI.
FIELD_PRESETS: dict[str, list[str]] = {
    "Built-in CheckRecord fields": [
        "test_id", "value", "expected", "passed",
        "msg", "scope", "msg_id", "detail",
    ],
    "Common user extras": [
        "operator", "notes", "address", "retries", "seq_id",
    ],
}

# The extra-context rows shown on the first GET. Two common keys with
# an empty value: the user fills them in, renames them or deletes the
# row — the point is to show the shape of a key/value pair.
DEFAULT_EXTRA_CONTEXT: list[dict[str, str]] = [
    {"key": "project", "value": ""},
    {"key": "operator", "value": ""},
]

# The built-in ``CheckRecord`` fields a report can expose, with the
# explanation the GUI shows next to each field name. The wording
# follows the ``CheckRecord`` docstring in ``hwval.checks`` — the
# authoritative description of what each attribute holds.
#
# ``hint`` is the short one-liner shown under the field name while
# the user types; ``what`` / ``source`` are the two columns of the
# reference table.
FIELD_REFERENCE: list[dict[str, str]] = [
    {
        "group": "Built-in CheckRecord fields",
        "name": "test_id",
        "what": "Id of the test that produced the record.",
        "source": "Derived by the test_id function — the default emits "
                  "TID_0001, TID_0002, … The same id lands in the log "
                  "lines.",
        "hint": "id of the test, from the test_id function",
    },
    {
        "group": "Built-in CheckRecord fields",
        "name": "scope",
        "what": "Grouping tag for the check.",
        "source": "The scope= argument of check_value / "
                  "check_value_in_range.",
        "hint": "grouping tag of the check",
    },
    {
        "group": "Built-in CheckRecord fields",
        "name": "msg_id",
        "what": "Id of the individual check.",
        "source": "The msg_id= argument of the check.",
        "hint": "id of the check",
    },
    {
        "group": "Built-in CheckRecord fields",
        "name": "msg",
        "what": "Human-readable message of the check.",
        "source": "The msg= argument of the check.",
        "hint": "message of the check",
    },
    {
        "group": "Built-in CheckRecord fields",
        "name": "value",
        "what": "The observed value that was compared.",
        "source": "The first operand of the check.",
        "hint": "the observed value",
    },
    {
        "group": "Built-in CheckRecord fields",
        "name": "expected",
        "what": "The value the observation was compared against.",
        "source": "The second operand of check_value; "
                  "check_value_in_range reports it as \"in [min, max]\".",
        "hint": "the value it was compared against",
    },
    {
        "group": "Built-in CheckRecord fields",
        "name": "passed",
        "what": "Whether the check passed.",
        "source": "True or False, straight from the comparison.",
        "hint": "did the check pass?",
    },
    {
        "group": "Built-in CheckRecord fields",
        "name": "detail",
        "what": "One-line detail of the comparison.",
        "source": "Generated by the check, e.g. "
                  "\"value=0x2A expected=0x2A\".",
        "hint": "one-line detail of the comparison",
    },
    {
        "group": "User extras (your own kwargs)",
        "name": "operator",
        "what": "Who ran the test.",
        "source": "Set by operator= on the check; lands in the "
                  "record's extras.",
        "hint": "user extra — set by operator= on the check",
    },
    {
        "group": "User extras (your own kwargs)",
        "name": "notes",
        "what": "Free-text note about the check.",
        "source": "Set by notes= on the check; lands in the record's "
                  "extras.",
        "hint": "user extra — set by notes= on the check",
    },
    {
        "group": "User extras (your own kwargs)",
        "name": "address",
        "what": "Register or memory address involved.",
        "source": "Set by address= on the check; lands in the record's "
                  "extras.",
        "hint": "user extra — set by address= on the check",
    },
    {
        "group": "User extras (your own kwargs)",
        "name": "retries",
        "what": "How often the check was retried.",
        "source": "Set by retries= on the check; lands in the record's "
                  "extras.",
        "hint": "user extra — set by retries= on the check",
    },
    {
        "group": "User extras (your own kwargs)",
        "name": "seq_id",
        "what": "Your own sequence id.",
        "source": "Set by seq_id= on the check; lands in the record's "
                  "extras.",
        "hint": "user extra — set by seq_id= on the check",
    },
]

# Short one-liner per known field, shown under the field name while
# the user types.
FIELD_HINTS: dict[str, str] = {
    entry["name"]: entry["hint"] for entry in FIELD_REFERENCE
}


# --------------------------------------------------------------------------- #
# Form ↔ YML helpers                                                          #
# --------------------------------------------------------------------------- #


def _read_form_fields() -> list[dict[str, str]]:
    """Pull the field rows out of the request.

    Empty / duplicate names are preserved here so the user sees the
    same row count on the round-trip; validation lives in
    :func:`_validate_and_build`.
    """
    names = request.form.getlist("field_name")
    reports = request.form.getlist("field_reports")
    out: list[dict[str, str]] = []
    for i in range(max(len(names), len(reports))):
        n = (names[i] if i < len(names) else "").strip()
        r = (reports[i] if i < len(reports) else "all").strip()
        if r not in ("all", "test_performed", "test_results"):
            r = "all"
        out.append({"name": n, "reports": r})
    return out


def _read_settings() -> dict[str, Any]:
    """Pull the include toggles and optional test_id_function."""
    return {
        "include_passed": request.form.get("include_passed") == "on",
        "include_failed": request.form.get("include_failed") == "on",
        "test_id_function": request.form.get("test_id_function", "").strip(),
    }


def _read_extra_context() -> list[dict[str, str]]:
    """Pull the extra-context key/value rows out of the request.

    Rows with an empty key are preserved here (so the form round-trips
    the same row count); they are skipped by the validation.
    """
    keys = request.form.getlist("ctx_key")
    values = request.form.getlist("ctx_value")
    out: list[dict[str, str]] = []
    for i in range(max(len(keys), len(values))):
        k = (keys[i] if i < len(keys) else "").strip()
        v = values[i] if i < len(values) else ""
        out.append({"key": k, "value": v})
    return out


def _coerce_context_value(raw: str) -> Any:
    """Turn a typed-in context value into a Python scalar.

    Only unambiguous literals are converted (``true`` / ``false`` /
    ``null``, integers, floats); everything else stays a string. The
    value ends up in the *Python kwargs* preview — the downloaded
    ``.docx`` template only carries the placeholder, the value is
    runtime data.
    """
    s = raw.strip()
    if s == "":
        return ""
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return raw


def _fmt_python_value(value: Any) -> str:
    """Format a Python value for the kwargs preview (double quotes)."""
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return repr(value)


def _render_index(
    fields: list[dict[str, str]],
    settings: dict[str, Any],
    extra_context: list[dict[str, str]],
    result: dict[str, Any] | None,
) -> str:
    """Render the form with the given state.

    Every route that shows the form goes through here so the
    template always gets the same set of variables.
    """
    return render_template(
        "index.html",
        fields=fields,
        settings=settings,
        extra_context=extra_context,
        report_options=REPORT_OPTIONS,
        presets=FIELD_PRESETS,
        field_reference=FIELD_REFERENCE,
        field_hints=FIELD_HINTS,
        default_fields={f["name"] for f in DEFAULT_FIELDS},
        result=result,
    )


def _fields_from_config(cfg: dict[str, Any]) -> list[dict[str, str]]:
    """Map a loaded config's ``FieldSpec`` list back to form rows.

    :attr:`hwval.docs.FieldSpec.reports` is a tuple of report
    names; the form only offers ``all`` / ``test_performed`` /
    ``test_results``. The two single-report tuples map onto their
    dropdown option and everything else (the default pair, an empty
    tuple, …) maps onto ``all``.
    """
    out: list[dict[str, str]] = []
    for spec in cfg.get("fields") or []:
        reports = set(getattr(spec, "reports", ()) or ())
        if reports == {"test_performed"}:
            scope = "test_performed"
        elif reports == {"test_results"}:
            scope = "test_results"
        else:
            scope = "all"
        out.append({"name": spec.name, "reports": scope})
    return out


def _validate_and_build(
    fields: list[dict[str, str]],
    settings: dict[str, Any],
    extra_context: list[dict[str, str]] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate form input, return ``(config_dict, errors)``.

    ``config_dict`` is a plain mapping ready to dump as YAML; it
    uses the *normalised* form ``load_seg_config`` produces, so
    passing the same shape back through ``load_seg_config`` on
    disk will succeed.

    The ``extra_context`` mapping is *not* part of the YML —
    ``hwval.docs.load_seg_config`` only accepts ``fields``,
    ``include_passed``, ``include_failed`` and ``test_id_function``.
    It is surfaced through the Python-kwargs preview and through the
    generated ``.docx`` templates instead.

    Returns ``(None, errors)`` if validation failed.
    """
    errors: list[str] = []

    # ---- fields ----
    if not any(f["name"] for f in fields):
        errors.append("Add at least one field.")

    coerced: list[Any] = []
    seen: set[str] = set()
    for i, f in enumerate(fields, start=1):
        name = f["name"]
        if not name:
            continue  # empty row, skip silently
        if not name.isidentifier():
            errors.append(
                f"Field #{i} ({name!r}): not a valid Python identifier."
            )
            continue
        if name in seen:
            errors.append(f"Field #{i} ({name!r}): duplicate name.")
            continue
        seen.add(name)
        reports = f["reports"]
        if reports not in ("all", "test_performed", "test_results"):
            errors.append(
                f"Field #{i} ({name!r}): invalid reports value {reports!r}."
            )
            continue
        coerced.append({"name": name, "reports": reports})

    if any(e for e in errors):
        return None, errors

    # ---- test_id_function ----
    tif = settings["test_id_function"]
    if tif:
        if ":" not in tif or tif.count(":") != 1:
            errors.append(
                "test_id_function must be in 'package.module:attr' form."
            )
            return None, errors
        mod, _, attr = tif.partition(":")
        if not mod or not attr:
            errors.append(
                "test_id_function must be in 'package.module:attr' form."
            )
            return None, errors

    # ---- extra_context ----
    coerced_ctx: dict[str, Any] = {}
    seen_ctx: set[str] = set()
    for i, c in enumerate(extra_context or [], start=1):
        key = c["key"]
        if not key:
            continue  # empty row, skip silently
        if not key.isidentifier() or keyword.iskeyword(key):
            errors.append(
                f"Extra context #{i} ({key!r}): not a valid Python "
                f"identifier."
            )
            continue
        if key in seen_ctx:
            errors.append(
                f"Extra context #{i} ({key!r}): duplicate key."
            )
            continue
        if key in docx_templates.RESERVED_CONTEXT_KEYS:
            errors.append(
                f"Extra context #{i} ({key!r}): reserved name — it "
                f"would shadow a built-in template variable."
            )
            continue
        seen_ctx.add(key)
        coerced_ctx[key] = _coerce_context_value(c["value"])

    if any(e for e in errors):
        return None, errors

    cfg: dict[str, Any] = {"fields": coerced}
    cfg["include_passed"] = settings["include_passed"]
    cfg["include_failed"] = settings["include_failed"]
    cfg["extra_context"] = coerced_ctx
    if tif:
        cfg["test_id_function"] = tif

    return cfg, errors


def _build_yaml_text(cfg: dict[str, Any]) -> str:
    """Serialise a config dict to a stable, human-friendly YML string.

    Field entries with ``reports == "all"`` are emitted as a plain
    string; entries scoped to a single report are emitted as a
    mapping so the YML matches the canonical form documented in
    :func:`hwval.docs.load_seg_config`.
    """
    lines: list[str] = ["fields:"]
    for entry in cfg["fields"]:
        if entry["reports"] == "all":
            lines.append(f"  - {entry['name']}")
        else:
            lines.append(f"  - name: {entry['name']}")
            lines.append(f"    reports: {entry['reports']}")
    lines.append("")
    lines.append(f"include_passed: "
                 f"{'true' if cfg['include_passed'] else 'false'}")
    lines.append(f"include_failed: "
                 f"{'true' if cfg['include_failed'] else 'false'}")
    if cfg.get("test_id_function"):
        lines.append("")
        lines.append(f'test_id_function: "{cfg["test_id_function"]}"')
    lines.append("")  # trailing newline
    return "\n".join(lines)


def _build_python_kwargs(cfg: dict[str, Any]) -> str:
    """Show the equivalent ``SegDocument(..., fields=[...])`` call.

    Pure-text, ready to paste into a Python file.
    """
    parts: list[str] = [
        "from hwval import SegDocument",
        "",
        "doc = SegDocument(",
        '    test_template="templates/test_performed.docx",',
        '    results_template="templates/test_results.docx",',
    ]
    if cfg["fields"]:
        parts.append("    fields=[")
        for entry in cfg["fields"]:
            if entry["reports"] == "all":
                parts.append(f'        "{entry["name"]}",')
            else:
                parts.append(
                    f'        {{"name": "{entry["name"]}", '
                    f'"reports": "{entry["reports"]}"}},'
                )
        parts.append("    ],")
    parts.append(
        f"    include_passed={str(cfg['include_passed']).capitalize()},"
    )
    parts.append(
        f"    include_failed={str(cfg['include_failed']).capitalize()},"
    )
    if cfg.get("extra_context"):
        parts.append("    extra_context={")
        for key, value in cfg["extra_context"].items():
            parts.append(f'        "{key}": {_fmt_python_value(value)},')
        parts.append("    },")
    if cfg.get("test_id_function"):
        parts.append(
            f'    test_id_function="{cfg["test_id_function"]}",'
        )
    parts.append(")")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Routes                                                                     #
# --------------------------------------------------------------------------- #


def index() -> str:
    """Render the form (GET) or process it and re-render with YML (POST)."""
    if request.method == "GET":
        fields = list(DEFAULT_FIELDS)
        settings = {"include_passed": True, "include_failed": True,
                    "test_id_function": ""}
        extra_context = [dict(c) for c in DEFAULT_EXTRA_CONTEXT]
        result = None
    else:
        fields = _read_form_fields()
        settings = _read_settings()
        extra_context = _read_extra_context()
        cfg, errors = _validate_and_build(fields, settings, extra_context)
        if errors:
            return _render_index(
                fields,
                settings,
                extra_context,
                {
                    "errors": errors,
                    "yaml": "",
                    "python": "",
                    "notice": "",
                    "heading": "Could not generate YML:",
                },
            )
        yaml_text = _build_yaml_text(cfg)
        python_text = _build_python_kwargs(cfg)

        # Re-validate the generated YML through the real loader
        # (defence in depth — the form-level checks above should
        # already catch the same problems, but if the loader gets
        # stricter the form will still produce a working YML).
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False, encoding="utf-8"
            ) as f:
                f.write(yaml_text)
                tmp = f.name
            load_seg_config(tmp)
        except Exception as e:  # pragma: no cover - defensive
            return _render_index(
                fields,
                settings,
                extra_context,
                {
                    "errors": [f"generated YML failed validation: {e}"],
                    "yaml": yaml_text,
                    "python": python_text,
                    "notice": "",
                    "heading": "Could not generate YML:",
                },
            )
        finally:
            if tmp:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

        result = {
            "errors": [],
            "yaml": yaml_text,
            "python": python_text,
            "notice": "",
            "heading": "",
        }

    return _render_index(fields, settings, extra_context, result)


def load_config() -> str:
    """Fill the form from an existing ``hwval.yml`` file.

    The upload is validated with the real
    :func:`hwval.docs.load_seg_config` loader — the same code the
    generated YML is checked against — so a file that loads here is a
    file that works at runtime. A file the loader rejects is reported
    with the loader's own message.

    The extra context is *not* part of the YML, so the rows the user
    already typed are carried over unchanged.
    """
    fields = list(DEFAULT_FIELDS)
    settings = {"include_passed": True, "include_failed": True,
                "test_id_function": ""}
    extra_context = _read_extra_context() or [
        dict(c) for c in DEFAULT_EXTRA_CONTEXT
    ]

    def fail(message: str) -> str:
        return _render_index(
            fields,
            settings,
            extra_context,
            {
                "errors": [message],
                "yaml": "",
                "python": "",
                "notice": "",
                "heading": "Could not load the config:",
            },
        )

    upload = request.files.get("yml_file")
    filename = (upload.filename if upload else "") or ""
    if upload is None or not filename:
        return fail("Choose a .yml file to load.")

    raw = upload.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return fail(f"{filename}: not a UTF-8 text file.")

    # The loader insists on a real path, so park the upload in a
    # temp file for the duration of the call.
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False, encoding="utf-8"
        ) as f:
            f.write(text)
            tmp = f.name
        cfg = load_seg_config(tmp)
    except Exception as e:
        message = str(e)
        if tmp:
            # The loader quotes the path it choked on — show the
            # uploaded file name instead of the temp path.
            message = message.replace(tmp, filename)
        if filename not in message:
            message = f"{filename}: {message}"
        return fail(message)
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    loaded = _fields_from_config(cfg)
    if not loaded:
        return fail(
            f"{filename}: no 'fields' entry — there is nothing to load."
        )

    fields = loaded
    settings = {
        "include_passed": bool(cfg.get("include_passed", True)),
        "include_failed": bool(cfg.get("include_failed", True)),
        "test_id_function": cfg.get("test_id_function") or "",
    }
    return _render_index(
        fields,
        settings,
        extra_context,
        {
            "errors": [],
            "yaml": "",
            "python": "",
            "notice": f"Loaded {len(fields)} field(s) from {filename}.",
            "heading": "",
        },
    )


def download() -> Response:
    """Return the YML submitted in the POST body as a downloadable file.

    Re-runs the same validation as :func:`index` so a malformed
    POST never writes a broken file. On validation failure the
    response is a 400 with the error list as text.
    """
    fields = _read_form_fields()
    settings = _read_settings()
    extra_context = _read_extra_context()
    cfg, errors = _validate_and_build(fields, settings, extra_context)
    if errors or cfg is None:
        return Response(
            "validation failed:\n  - " + "\n  - ".join(errors),
            status=400,
            mimetype="text/plain",
        )
    yaml_text = _build_yaml_text(cfg)
    return send_file(
        BytesIO(yaml_text.encode("utf-8")),
        as_attachment=True,
        download_name="hwval.yml",
        mimetype="text/yaml",
    )


def download_template(report: str) -> Response:
    """Return a starter ``.docx`` template for ``report``.

    The document contains the fields the user declared — scoped to
    the requested report — as table columns with a
    ``{{ rec.<field> }}`` placeholder each, plus a
    ``{{ <key> }}`` placeholder for every extra-context key.

    ``report`` is ``"test_performed"`` or ``"test_results"``; the
    two files are the ``test_template`` / ``results_template``
    arguments of :class:`hwval.docs.SegDocument`.
    """
    if report not in docx_templates.REPORTS:
        return Response(
            f"unknown report {report!r}; valid: "
            f"{', '.join(docx_templates.REPORTS)}",
            status=404,
            mimetype="text/plain",
        )

    fields = _read_form_fields()
    settings = _read_settings()
    extra_context = _read_extra_context()
    cfg, errors = _validate_and_build(fields, settings, extra_context)
    if errors or cfg is None:
        return Response(
            "validation failed:\n  - " + "\n  - ".join(errors),
            status=400,
            mimetype="text/plain",
        )

    try:
        data = docx_templates.build_template_docx(
            report, cfg["fields"], cfg["extra_context"]
        )
    except ImportError as e:  # pragma: no cover - optional dep guard
        return Response(
            "Building the .docx template needs the optional [docs] "
            "extra: install it with `uv sync --extra docs`.\n" + str(e),
            status=500,
            mimetype="text/plain",
        )

    return send_file(
        BytesIO(data),
        as_attachment=True,
        download_name=docx_templates.template_filename(report),
        mimetype=DOCX_MIMETYPE,
    )


def healthz() -> dict[str, str]:
    """Cheap liveness probe (handy for ``curl``-based smoke tests)."""
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Module-level WSGI app for ``flask run`` and friends                        #
# --------------------------------------------------------------------------- #


app = create_app()


if __name__ == "__main__":
    # ``debug=False`` because the form has a file-rewrite step
    # (defence-in-depth re-validation) and reloader subprocesses
    # would race on the temp file. ``host=0.0.0.0`` makes the app
    # reachable from another machine on the LAN if you want to
    # point a tablet / phone at it; switch to ``127.0.0.1`` for
    # localhost-only.
    app.run(host="127.0.0.1", port=5000, debug=False)

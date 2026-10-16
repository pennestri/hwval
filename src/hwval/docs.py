"""Generate docx test reports via Jinja2+docx templates.

This module provides :class:`SegDocument`, which renders two `.docx` files
(``test performed`` + ``test results``) from user-supplied templates. The
templates are ordinary Word documents with Jinja2 placeholders inside text
runs, processed via `docxtpl
<https://docxtpl.readthedocs.io/>`_.

Requires the optional :code:`hwval[docs]` extra
(:code:`pip install hwval[docs]` / :code:`uv add hwval[docs]`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple, Union

from .checks import (
    CheckRecord,
    TestSummary,
    TestIdFunction,
    current_summary,
    set_test_id_function,
)


# --------------------------------------------------------------------------- #
# Public dataclasses                                                           #
# --------------------------------------------------------------------------- #


@dataclass
class _TemplateContext:
    """Internal: what's handed to each Jinja2 template during rendering."""

    summary: TestSummary
    passed: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    records: list[dict] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    include_passed: bool = True
    include_failed: bool = True
    generated_at: str = ""


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


# Default set of CheckRecord fields exposed to Jinja templates.
# ``test_id`` is the user-supplied id of the test (filled in by
# :func:`hwval.set_test_id_function`); it is included by default so
# the rendered report carries the id without extra wiring.
DEFAULT_FIELDS: tuple[str, ...] = (
    "test_id",
    "msg",
    "scope",
    "msg_id",
    "passed",
    "detail",
)


# Recognized keys in a YML SegDocument config (see ``load_seg_config``).
# Anything else is a hard error so typos don't get silently ignored.
SEG_CONFIG_KEYS: frozenset[str] = frozenset(
    {"fields", "include_passed", "include_failed", "test_id_function"}
)


def _record_to_dict(record: CheckRecord, fields: Sequence[str]) -> dict:
    """Project a CheckRecord onto the requested subset of fields."""
    out: dict[str, Any] = {}
    for name in fields:
        if not hasattr(record, name):
            raise AttributeError(
                f"CheckRecord has no field {name!r}; "
                f"valid fields are: {sorted(f.__name__ for f in record.__dataclass_fields__.values())}"
            )
        out[name] = getattr(record, name)
    return out


def _select(
    records: Sequence[CheckRecord],
    *,
    include: bool,
    filter_fn: Optional[Callable[[CheckRecord], bool]],
) -> list[CheckRecord]:
    """Apply ``include`` toggle and optional ``filter_fn`` to a record list."""
    if include and filter_fn is None:
        return list(records)
    out: list[CheckRecord] = []
    for r in records:
        if not include:
            continue
        if filter_fn is not None and not filter_fn(r):
            continue
        out.append(r)
    return out


# --------------------------------------------------------------------------- #
# YML config support                                                           #
# --------------------------------------------------------------------------- #
#
# A user-supplied YAML file may drive the same knobs the SegDocument
# constructor exposes (``fields``, ``include_passed``, ``include_failed``,
# ``test_id_function``). This is convenient when a project wants to
# adjust the report layout without touching Python code: edit the YAML,
# re-run the test, the report layout updates.
#
# Example ``hwval.yml``::
#
#     fields:
#       - test_id
#       - msg
#       - scope
#       - msg_id
#       - passed
#       - detail
#     include_passed: true
#     include_failed: true
#     test_id_function: "my_pkg.helpers:make_test_id"


def _resolve_callable(dotted_path: str) -> Callable[..., Any]:
    """Resolve ``"package.module:attr"`` to a live Python object.

    The format mirrors the one used by ``logging.config.dictConfig`` and
    ``pickle`` so anyone already familiar with those tools is at home.
    """
    if not isinstance(dotted_path, str) or ":" not in dotted_path:
        raise ValueError(
            f"callable path must be in 'package.module:attr' form, "
            f"got {dotted_path!r}"
        )
    module_path, _, attr = dotted_path.partition(":")
    if not module_path or not attr:
        raise ValueError(
            f"callable path must be in 'package.module:attr' form, "
            f"got {dotted_path!r}"
        )
    import importlib

    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise ImportError(
            f"cannot import module {module_path!r} for test_id_function"
        ) from e
    try:
        fn = getattr(module, attr)
    except AttributeError as e:
        raise AttributeError(
            f"module {module_path!r} has no attribute {attr!r}"
        ) from e
    if not callable(fn):
        raise TypeError(
            f"dotted path {dotted_path!r} resolved to "
            f"{type(fn).__name__}, not a callable"
        )
    return fn


def load_seg_config(path: Union[str, Path]) -> dict[str, Any]:
    """Load a SegDocument configuration from a YAML file.

    The file is expected to map onto the same keys the
    :class:`SegDocument` constructor accepts:

    * ``fields`` (list[str]) — names of :class:`CheckRecord` fields to
      expose to the templates.
    * ``include_passed`` (bool) — default ``True``.
    * ``include_failed`` (bool) — default ``True``.
    * ``test_id_function`` (str) — a ``"package.module:attr"`` reference
      to a function with signature ``(record, sequence) -> str``. It is
      installed globally via :func:`hwval.set_test_id_function` so the
      same id ends up in logs and reports.

    Any unknown key raises :class:`ValueError` so typos surface early
    instead of being silently ignored.

    Requires PyYAML; raise a clear :class:`ImportError` if it isn't
    installed. PyYAML is *not* a hard dependency of ``hwval`` because
    the YAML loader only matters if you opt in via ``config=`` /
    :func:`load_seg_config`.

    Parameters
    ----------
    path:
        Path to a YAML file. ``"-"`` and :class:`io.StringIO` are not
        accepted; pass a real path so error messages stay useful.

    Returns
    -------
    dict
        A validated config dict ready to merge into SegDocument kwargs.
    """
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as e:
        raise ImportError(
            "SegDocument YAML config requires PyYAML. "
            "Install with `pip install pyyaml` or `uv add pyyaml`."
        ) from e

    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"SegDocument config not found: {p}")

    with p.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if cfg is None:
        cfg = {}
    if not isinstance(cfg, dict):
        raise TypeError(
            f"SegDocument YAML root must be a mapping, "
            f"got {type(cfg).__name__}"
        )

    unknown = set(cfg) - SEG_CONFIG_KEYS
    if unknown:
        raise ValueError(
            f"unknown SegDocument config key(s) in {p}: "
            f"{sorted(unknown)}; valid keys: {sorted(SEG_CONFIG_KEYS)}"
        )

    if "fields" in cfg:
        flds = cfg["fields"]
        if not isinstance(flds, list) or not all(
            isinstance(x, str) for x in flds
        ):
            raise TypeError(
                f"`fields` in {p} must be a list[str], got "
                f"{type(flds).__name__}"
            )
    for key in ("include_passed", "include_failed"):
        if key in cfg and not isinstance(cfg[key], bool):
            raise TypeError(
                f"`{key}` in {p} must be a bool, got "
                f"{type(cfg[key]).__name__}"
            )
    if "test_id_function" in cfg and not isinstance(
        cfg["test_id_function"], str
    ):
        raise TypeError(
            f"`test_id_function` in {p} must be a string "
            f"('package.module:attr'), got "
            f"{type(cfg['test_id_function']).__name__}"
        )
    return cfg


def _normalize_test_id_function(
    func: Union[None, str, TestIdFunction, Callable[..., Any]],
) -> Optional[TestIdFunction]:
    """Coerce a ``test_id_function`` kwarg to a real callable (or ``None``).

    Accepts a callable (used as-is), a ``"package.module:attr"`` string
    (resolved via :func:`_resolve_callable`), or ``None`` (meaning
    "do not install a function; keep the current default").
    """
    if func is None:
        return None
    if isinstance(func, str):
        return _resolve_callable(func)
    if callable(func):
        return func
    raise TypeError(
        f"test_id_function must be a callable, a 'module:attr' string, "
        f"or None; got {type(func).__name__}"
    )


# --------------------------------------------------------------------------- #
# SegDocument                                                                  #
# --------------------------------------------------------------------------- #


class SegDocument:
    """Render two docx reports from user-supplied Jinja2+docx templates.

    A :class:`SegDocument` binds together two ``.docx`` templates plus the
    reporting options, then renders them on demand via :meth:`_generate`.
    The two outputs are:

    1. **Test performed** — describes the tests that ran.
    2. **Test results** — the actual outcomes (passed / failed).

    Both templates receive the same Jinja context, so the only difference
    between the two outputs is what the user puts in each template.

    The templates are ordinary Word documents containing Jinja2 placeholders
    (use `docxtpl` syntax: ``{{ var }}`` for variables, ``{%p ... %}`` for
    paragraph-level control). The placeholders available are documented in
    :meth:`_generate`.

    Parameters
    ----------
    test_template:
        Path to the ``test performed`` ``.docx`` template.
    results_template:
        Path to the ``test results`` ``.docx`` template.
    fields:
        Subset of :class:`CheckRecord` field names to expose to the
        templates. Default: ``("test_id", "msg", "scope", "msg_id",
        "passed", "detail")``. Anything not listed is not visible
        inside the template.
    include_passed:
        When ``False``, passing records are excluded from both rendered
        documents.
    include_failed:
        When ``False``, failing records are excluded from both rendered
        documents.
    filter:
        Optional ``Callable[[CheckRecord], bool]`` for further filtering.
        Runs after the include toggles. Useful for scoping reports to a
        subset (e.g. only register tests: ``filter=lambda r: r.scope ==
        "reg_walk"``).
    extra_context:
        Extra keys merged into the Jinja context. Use for project name,
        device under test, operator, etc.
    test_id_function:
        User-supplied function used to derive the ``test_id`` of every
        WARNING-level :class:`CheckRecord`. Signature is
        ``(record, sequence) -> str``. May be a callable (used as-is)
        or a ``"package.module:attr"`` string (resolved on
        construction). When supplied it is installed globally via
        :func:`hwval.set_test_id_function` so the same id ends up in
        both the rendered report and any captured log records. Pass
        ``None`` (the default) to leave the current function in place
        (built-in sequential ``"TID_<seq:04d>"`` unless already
        overridden).
    config:
        Path to a YAML file driving any of ``fields``,
        ``include_passed``, ``include_failed``, ``test_id_function``.
        Loaded via :func:`load_seg_config`. Convenient for keeping the
        report layout out of Python source — edit the YAML, re-run the
        test, the report updates. Explicit kwargs always win over the
        YAML (the YAML only fills in keys that were left at their
        defaults). Requires PyYAML; raises a clear ``ImportError``
        otherwise.

    Raises
    ------
    ImportError
        If the optional :code:`hwval[docs]` extra is not installed.
    ImportError
        If ``config`` is supplied but PyYAML is not installed.
    FileNotFoundError
        If ``config`` is supplied and the file does not exist.
    ValueError
        If the YAML config contains unknown keys, or
        ``test_id_function`` does not parse to a callable.

    Examples
    --------
    >>> doc = SegDocument(
    ...     test_template="templates/test_performed.docx",
    ...     results_template="templates/test_results.docx",
    ...     fields=("msg", "scope", "msg_id", "passed"),
    ...     filter=lambda r: r.scope == "reg_walk",
    ...     extra_context={"project": "Acme DUT v3", "operator": "alice"},
    ... )
    >>> test_path, results_path = doc._generate(
    ...     test_output="out/test_performed.docx",
    ...     results_output="out/test_results.docx",
    ... )
    """

    def __init__(
        self,
        test_template: Union[str, Path],
        results_template: Union[str, Path],
        *,
        fields: Optional[Sequence[str]] = None,
        include_passed: bool = True,
        include_failed: bool = True,
        filter: Optional[Callable[[CheckRecord], bool]] = None,
        extra_context: Optional[Mapping[str, Any]] = None,
        test_id_function: Union[None, str, TestIdFunction, Callable[..., Any]] = None,
        config: Union[None, str, Path] = None,
    ) -> None:
        # Lazy import: keep the base library dependency-free.
        try:
            from docxtpl import DocxTemplate  # noqa: F401
        except ImportError as e:  # pragma: no cover - import guard
            raise ImportError(
                "SegDocument requires the optional [docs] extra: "
                "install with `pip install hwval[docs]` "
                "(provides docxtpl, python-docx, jinja2)."
            ) from e

        # ----- 1. Layer the YAML config under the explicit kwargs -----
        # The YAML only fills in keys the user did not already set
        # explicitly. This way the constructor signature is the
        # source of truth and the YAML is a convenience layer.
        if config is not None:
            cfg = load_seg_config(config)
            if fields is None and "fields" in cfg:
                fields = list(cfg["fields"])
            if "include_passed" in cfg:
                include_passed = cfg["include_passed"]
            if "include_failed" in cfg:
                include_failed = cfg["include_failed"]
            if test_id_function is None and "test_id_function" in cfg:
                test_id_function = cfg["test_id_function"]

        # ----- 2. Resolve test_id_function and install globally -----
        # A user-supplied function is global (set in checks.py module
        # state) so the same id ends up in the report, the log lines
        # emitted by check_value, and report_test_summary output.
        resolved_tid_fn = _normalize_test_id_function(test_id_function)
        if resolved_tid_fn is not None:
            set_test_id_function(resolved_tid_fn)

        self.test_template = Path(test_template)
        self.results_template = Path(results_template)

        self.fields: list[str] = (
            list(fields) if fields is not None else list(DEFAULT_FIELDS)
        )
        self.include_passed = include_passed
        self.include_failed = include_failed
        self.filter = filter
        self.extra_context: dict[str, Any] = (
            dict(extra_context) if extra_context else {}
        )
        # Keep the resolved callable around so callers can introspect
        # or override later via get_test_id_function.
        self.test_id_function: Optional[TestIdFunction] = resolved_tid_fn

    # ------------------------------------------------------------------ #
    # Internal                                                            #
    # ------------------------------------------------------------------ #

    def _build_context(
        self,
        summary: TestSummary,
        fields: Sequence[str],
    ) -> dict[str, Any]:
        """Compose the Jinja context for both templates.

        ``summary`` in the Jinja context reflects the *filtered* set of
        records (i.e. what is actually written to the rendered docx).
        ``records``, ``passed`` and ``failed`` are the same filtered sets
        as plain dicts projected onto ``fields``.
        """
        passed_records = _select(
            summary.passed,
            include=self.include_passed,
            filter_fn=self.filter,
        )
        failed_records = _select(
            summary.failed,
            include=self.include_failed,
            filter_fn=self.filter,
        )
        passed_dicts = [_record_to_dict(r, fields) for r in passed_records]
        failed_dicts = [_record_to_dict(r, fields) for r in failed_records]

        filtered_summary = TestSummary(passed=passed_dicts, failed=failed_dicts)

        ctx: dict[str, Any] = {
            "summary": filtered_summary,
            "passed": passed_dicts,
            "failed": failed_dicts,
            "records": passed_dicts + failed_dicts,
            "fields": list(fields),
            "include_passed": self.include_passed,
            "include_failed": self.include_failed,
            "generated_at": datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ),
        }
        ctx.update(self.extra_context)
        return ctx

    def _render_one(
        self,
        template_path: Path,
        output_path: Path,
        context: Mapping[str, Any],
    ) -> Path:
        """Render a single template and write it to disk."""
        from docxtpl import DocxTemplate

        if not template_path.is_file():
            raise FileNotFoundError(f"template not found: {template_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        tpl = DocxTemplate(str(template_path))
        tpl.render(dict(context))
        tpl.save(str(output_path))
        return output_path

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def _generate(
        self,
        test_output: Union[str, Path],
        results_output: Union[str, Path],
        *,
        summary: Optional[TestSummary] = None,
    ) -> Tuple[Path, Path]:
        """Render both templates and write the two docx outputs.

        Parameters
        ----------
        test_output:
            Destination path for the rendered ``test performed`` document.
        results_output:
            Destination path for the rendered ``test results`` document.
        summary:
            Source of records. If ``None`` (default), the current
            WARNING-test accumulator is snapshotted via
            :func:`hwval.current_summary` (without clearing it). Pass a
            custom :class:`TestSummary` to render an arbitrary set of
            records.

        Returns
        -------
        Tuple[Path, Path]
            ``(test_output_path, results_output_path)`` of the rendered
            documents.

        Jinja context available to both templates
        -----------------------------------------
        ``summary`` : :class:`TestSummary`
            A :class:`TestSummary` reflecting the *filtered* records
            (what is actually written to the rendered docx). Its
            ``passed`` / ``failed`` lists hold plain dicts projected
            onto the configured ``fields``. Counts (``total``,
            ``passed_count``, ``failed_count``, ``ok``) therefore match
            the rendered document.
        ``passed``  : list of dict
            Passing records projected onto the configured ``fields``.
        ``failed``  : list of dict
            Failing records projected onto the configured ``fields``.
        ``records`` : list of dict
            ``passed + failed``.
        ``fields``  : list of str
            The field names used to project records (echo for templates
            that want to render the column header row).
        ``include_passed`` / ``include_failed`` : bool
            Echo of the toggles, so templates can branch on them.
        ``generated_at`` : str
            ISO 8601 UTC timestamp of generation.
        Plus anything supplied via ``extra_context`` on the
        :class:`SegDocument` constructor.
        """
        if summary is None:
            summary = current_summary()

        context = self._build_context(summary, self.fields)

        test_path = self._render_one(
            self.test_template, Path(test_output), context
        )
        results_path = self._render_one(
            self.results_template, Path(results_output), context
        )
        return test_path, results_path
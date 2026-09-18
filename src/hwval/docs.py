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

from .checks import CheckRecord, TestSummary, current_summary


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
DEFAULT_FIELDS: tuple[str, ...] = (
    "msg",
    "scope",
    "msg_id",
    "passed",
    "detail",
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
        templates. Default: ``("msg", "scope", "msg_id", "passed",
        "detail")``. Anything not listed is not visible inside the
        template.
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

    Raises
    ------
    ImportError
        If the optional :code:`hwval[docs]` extra is not installed.

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
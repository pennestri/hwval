"""Bare-minimum Python port of UVVM's check methods.

Behaviour:
  * `check_value` and `check_value_in_range` return True on pass, False on fail.
  * On FAIL they log at the requested alert level AND raise AssertionError when
    the alert level is *_FAILURE / *_ERROR. WARNING/NOTE/INFO/DEBUG only log.
  * Log records are emitted through a module-level logger named `hwval`,
    so tests can capture them via `caplog` or by attaching their own handler.
"""

from __future__ import annotations

import dataclasses
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, TextIO


# --------------------------------------------------------------------------- #
# Enums (mirrors UVVM types_pkg)                                               #
# --------------------------------------------------------------------------- #


class AlertLevel(Enum):
    """UVVM-style alert severity. Mapped to stdlib logging levels."""

    TB_FAILURE = "TB_FAILURE"
    FAILURE = "FAILURE"
    TB_ERROR = "TB_ERROR"
    ERROR = "ERROR"
    TB_WARNING = "TB_WARNING"
    WARNING = "WARNING"
    NOTE = "NOTE"
    INFO = "INFO"
    DEBUG = "DEBUG"
    LOGICAL = "LOGICAL"


class MatchStrictness(Enum):
    """How `std_logic` values compare.

    * MATCH_STD    - 'H' equals '1' (loose, matches VHDL `std_match`).
    * MATCH_EXACT  - bit-for-bit equal (matches VHDL `=`).
    """

    MATCH_STD = "MATCH_STD"
    MATCH_EXACT = "MATCH_EXACT"


class Radix(Enum):
    """Display radix for log formatting."""

    HEX = "HEX"
    BIN = "BIN"
    DEC = "DEC"
    OCT = "OCT"
    UNSIGNED = "UNSIGNED"
    SIGNED = "SIGNED"
    ASCII = "ASCII"
    HEX_BIN_IF_INVALID = "HEX_BIN_IF_INVALID"


# --------------------------------------------------------------------------- #
# Internal helpers                                                             #
# --------------------------------------------------------------------------- #


_LOGGER_NAME = "hwval"
_logger = logging.getLogger(_LOGGER_NAME)

_ALERT_TO_LEVEL: dict[AlertLevel, int] = {
    AlertLevel.TB_FAILURE: logging.CRITICAL,
    AlertLevel.FAILURE: logging.CRITICAL,
    AlertLevel.TB_ERROR: logging.ERROR,
    AlertLevel.ERROR: logging.ERROR,
    AlertLevel.TB_WARNING: logging.WARNING,
    AlertLevel.WARNING: logging.WARNING,
    AlertLevel.NOTE: logging.INFO,
    AlertLevel.INFO: logging.INFO,
    AlertLevel.DEBUG: logging.DEBUG,
    AlertLevel.LOGICAL: logging.DEBUG,
}

_RAISING_LEVELS: frozenset[AlertLevel] = frozenset(
    {AlertLevel.TB_FAILURE, AlertLevel.FAILURE, AlertLevel.TB_ERROR, AlertLevel.ERROR}
)

# Alert levels whose outcomes are accumulated for `report_test_summary`.
_TRACKED_LEVELS: frozenset[AlertLevel] = frozenset(
    {AlertLevel.TB_WARNING, AlertLevel.WARNING}
)


@dataclass(frozen=True)
class CheckRecord:
    """A single WARNING-level check outcome, recorded for `report_test_summary`.

    `test_id` is derived at accumulation time by the user-supplied
    :data:`test_id_function` (or, by default, a sequential
    ``"TID_<seq>"``). The function receives the record (with
    ``test_id == ""``) and a 1-indexed sequence number; whatever it
    returns is stored as the record's ``test_id``. Reset
    :func:`reset_test_summary` also resets that sequence.

    `extras` holds the user-supplied YML-declared fields passed as
    ``**kwargs`` to :func:`check_value` / :func:`check_value_in_range`
    (e.g. ``operator="alice"``, ``notes="tested 3 times"``). Each
    entry is preserved as-is on the record and surfaced by
    :class:`hwval.docs.SegDocument` whenever the matching YML
    field-name requests it for a given report. Fields declared in
    the YML but absent from a particular check default to the empty
    string in the rendered report.
    """

    scope: str
    msg_id: str
    msg: str
    passed: bool
    detail: str
    test_id: str = ""
    extras: Mapping[str, Any] = field(default_factory=dict)


_summary_records: List[CheckRecord] = []


# --------------------------------------------------------------------------- #
# test_id function                                                            #
# --------------------------------------------------------------------------- #
#
# A user-supplied callable ``(record: CheckRecord, seq: int) -> str`` that
# fills in each WARNING-level ``CheckRecord.test_id``. The sequence counter
# starts at 1 on every :func:`reset_test_summary` call (or on process
# start) and is global so records keep a stable id across many checks
# inside one test run. The default function emits a sequential
# ``"TID_<seq:04d>"`` id; install your own with
# :func:`set_test_id_function`.


TestIdFunction = Callable[[CheckRecord, int], str]


def _default_test_id(record: CheckRecord, seq: int) -> str:
    """Sequential default: ``"TID_0001"``, ``"TID_0002"``, ..."""
    return f"TID_{seq:04d}"


_test_id_function: TestIdFunction = _default_test_id
_test_id_counter: int = 0


def set_test_id_function(
    func: Optional[TestIdFunction] = None,
) -> None:
    """Install the function used to derive ``test_id`` on every WARNING record.

    The function signature is ``(record, sequence) -> str`` where
    ``record`` is a :class:`CheckRecord` with ``test_id == ""`` (the
    field you are computing) and ``sequence`` is a 1-indexed counter
    that resets whenever :func:`reset_test_summary` is called.

    Passing ``None`` (the default) restores the built-in sequential
    function :data:`DEFAULT_TEST_ID_FUNCTION`.

    When the function is *changed* (i.e. a different callable is
    installed), every record already in the accumulator is re-stamped
    with the new function. Each record keeps its 1-indexed sequence
    position; only the ``test_id`` string is recomputed. This keeps
    the accumulator consistent with whichever function is currently
    active, so a report rendered immediately after
    ``set_test_id_function`` reflects the new id scheme. If a record's
    re-stamp raises, that record falls back to the default function
    and a DEBUG log line is emitted.

    Examples
    --------
    >>> from hwval import set_test_id_function
    >>> def by_scope_and_msg(record, seq):
    ...     return f"{record.scope}.{record.msg_id}.{seq:04d}"
    >>> set_test_id_function(by_scope_and_msg)
    """
    global _test_id_function
    new_fn = func if func is not None else _default_test_id
    if new_fn is _test_id_function:
        return
    # Re-apply to existing records so the whole accumulator reflects
    # the new function. Each record keeps its 1-indexed position.
    for i, rec in enumerate(_summary_records):
        seq = i + 1
        try:
            new_tid = str(new_fn(rec, seq))
        except Exception as e:  # pragma: no cover - defensive
            _logger.debug(
                "test_id_function raised %r while re-stamping; "
                "using default",
                e,
            )
            new_tid = _default_test_id(rec, seq)
        _summary_records[i] = dataclasses.replace(rec, test_id=new_tid)
    _test_id_function = new_fn


def get_test_id_function() -> TestIdFunction:
    """Return the currently installed test_id function.

    Always returns a callable (defaults to :data:`DEFAULT_TEST_ID_FUNCTION`
    when no user function has been installed).
    """
    return _test_id_function


def _next_test_id_seq() -> int:
    global _test_id_counter
    _test_id_counter += 1
    return _test_id_counter


@dataclass
class TestSummary:
    """Structured result returned by `report_test_summary`."""

    # pytest collects classes named Test* by default; opt out so users can
    # import this freely without pytest complaint.
    __test__ = False

    passed: List[CheckRecord] = field(default_factory=list)
    failed: List[CheckRecord] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.passed) + len(self.failed)

    @property
    def passed_count(self) -> int:
        return len(self.passed)

    @property
    def failed_count(self) -> int:
        return len(self.failed)

    @property
    def ok(self) -> bool:
        """True iff there are no failed WARNING checks."""
        return not self.failed


def set_logger(logger: logging.Logger) -> None:
    """Replace the module logger (used by tests to attach handlers)."""
    global _logger
    _logger = logger


def _format_scalar(value: Any, radix: Radix) -> str:
    """Format a single value for the log line."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        if radix == Radix.HEX:
            return f"0x{value:X}"
        if radix == Radix.BIN:
            return f"0b{value:b}"
        if radix == Radix.OCT:
            return f"0o{value:o}"
        return str(value)
    return repr(value)


def _format_value(value: Any, radix: Radix) -> str:
    """Format a scalar or sequence. UVVM treats arrays as MSB-first vectors."""
    if isinstance(value, (list, tuple)):
        sep = "" if radix in (Radix.HEX, Radix.BIN, Radix.OCT) else ", "
        return f"[{sep.join(_format_scalar(v, radix) for v in value)}]"
    return _format_scalar(value, radix)


def _emit(
    passed: bool,
    value: Any,
    exp: Any,
    alert_level: AlertLevel,
    msg: str,
    scope: str,
    msg_id: str,
    radix: Radix,
    match: Optional[MatchStrictness],
    extras: Optional[Mapping[str, Any]] = None,
) -> None:
    level = _ALERT_TO_LEVEL[alert_level]
    status = "PASS" if passed else "FAIL"
    val_s = _format_value(value, radix)
    exp_s = _format_value(exp, radix) if not isinstance(exp, str) or not exp.startswith("in [") else exp

    head = f"[{scope}] {msg_id} {status}: {msg}".rstrip(": ")
    detail = f"  value={val_s} expected={exp_s}"
    if match is not None:
        detail += f"  match={match.value}"

    _logger.log(level, "%s%s", head, detail)

    if alert_level in _TRACKED_LEVELS:
        # Copy extras so the frozen dataclass doesn't hold an alias to
        # the caller's mutable dict.
        extras_dict: Dict[str, Any] = dict(extras) if extras else {}
        rec = CheckRecord(
            scope=scope,
            msg_id=msg_id,
            msg=msg,
            passed=passed,
            detail=detail,
            extras=extras_dict,
        )
        # Apply the user-supplied test_id function (or the default).
        # The function may rely on any of the record's fields plus the
        # 1-indexed sequence counter, which resets on reset_test_summary.
        seq = _next_test_id_seq()
        try:
            test_id = _test_id_function(rec, seq)
        except Exception as e:  # pragma: no cover - defensive
            # A buggy test_id function must never corrupt a check;
            # fall back to the default so the report still has an id.
            # Reuse the seq we already allocated (don't burn another).
            _logger.debug("test_id_function raised %r; using default", e)
            test_id = _default_test_id(rec, seq)
        rec = dataclasses.replace(rec, test_id=str(test_id))
        _summary_records.append(rec)

    if not passed and alert_level in _RAISING_LEVELS:
        raise AssertionError(f"{head}{detail}")


# --------------------------------------------------------------------------- #
# Test summary (public API)                                                    #
# --------------------------------------------------------------------------- #


def reset_test_summary() -> None:
    """Clear the WARNING-test summary accumulator.

    Also resets the test_id sequence counter used by the default
    :data:`DEFAULT_TEST_ID_FUNCTION` and any user-supplied function
    installed via :func:`set_test_id_function`. The next WARNING
    check after a reset is sequence 1.
    """
    global _test_id_counter
    _summary_records.clear()
    _test_id_counter = 0


def current_summary() -> TestSummary:
    """Return a snapshot of the current WARNING-test accumulator.

    Unlike :func:`report_test_summary`, this does not print and does not
    reset the accumulator. Useful for downstream tooling that wants the
    accumulated records without consuming them (e.g.
    :class:`hwval.docs.SegDocument`).
    """
    passed = [r for r in _summary_records if r.passed]
    failed = [r for r in _summary_records if not r.passed]
    return TestSummary(passed=passed, failed=failed)


def report_test_summary(
    *,
    file: Optional[TextIO] = None,
    reset: bool = True,
    fail_on_failed: bool = False,
) -> TestSummary:
    """Print and return a summary of WARNING-level checks seen so far.

    Both `check_value` and `check_value_in_range` accumulate their
    `WARNING`/`TB_WARNING` outcomes in module state. This function prints the
    accumulated checks (passing and failing) and, by default, clears the
    accumulator.

    Parameters
    ----------
    file:
        Stream to write the human-readable report to. Defaults to
        `sys.stdout`. Pass `io.StringIO()` to capture without printing.
    reset:
        Clear the accumulator after reporting. Default `True`.
    fail_on_failed:
        Raise `AssertionError` if any WARNING check failed. Default `False`,
        leaving the decision to the caller (the returned `TestSummary.ok`
        flag is a non-raising alternative).

    Returns
    -------
    TestSummary
        Structured result with `passed` and `failed` `CheckRecord` lists and
        convenience counts (`passed_count`, `failed_count`, `total`, `ok`).
    """
    if file is None:
        file = sys.stdout

    passed = [r for r in _summary_records if r.passed]
    failed = [r for r in _summary_records if not r.passed]

    print(
        f"Test Summary: {len(passed)} passed, {len(failed)} failed",
        file=file,
    )

    if failed:
        print(f"\nFAILED ({len(failed)}):", file=file)
        for r in failed:
            head = f"[{r.scope}] {r.msg_id} {r.msg}".rstrip(": ")
            print(f"  {head}", file=file)
            print(f"    {r.detail}", file=file)

    if passed:
        print(f"\nPASSED ({len(passed)}):", file=file)
        for r in passed:
            head = f"[{r.scope}] {r.msg_id} {r.msg}".rstrip(": ")
            print(f"  {head}", file=file)
            print(f"    {r.detail}", file=file)

    summary = TestSummary(passed=passed, failed=failed)

    if reset:
        global _test_id_counter
        _summary_records.clear()
        _test_id_counter = 0

    if fail_on_failed and failed:
        raise AssertionError(
            f"{len(failed)} WARNING check(s) failed; see {file} for details"
        )

    return summary


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #


def check_value(
    value: Any,
    exp: Any,
    *args: Any,
    alert_level: AlertLevel = AlertLevel.ERROR,
    msg: str = "",
    scope: str = "C_TB_SCOPE_DEFAULT",
    msg_id: str = "ID_POS_ACK",
    radix: Radix = Radix.HEX_BIN_IF_INVALID,
    match_strictness: MatchStrictness = MatchStrictness.MATCH_STD,
    **extras: Any,
) -> bool:
    """Check that `value == exp`.

    Positional extra args (UVVM compatibility): if the first positional after
    `exp` is a `MatchStrictness`, it is consumed as `match_strictness`.

    Keyword-only ``**extras`` captures user-supplied YML-declared fields
    (e.g. ``operator="alice"``, ``notes="retried 3x"``) and stores them
    on the record's :attr:`CheckRecord.extras` dict. They never clash
    with the named parameters above; any kwarg whose name does not
    match a named parameter lands in ``extras``.

    Returns True on pass, False on fail. On FAIL with *_FAILURE/*_ERROR
    severity, also raises AssertionError.
    """
    if args:
        if isinstance(args[0], MatchStrictness):
            match_strictness = args[0]
            args = args[1:]
        if args:
            raise TypeError(
                "check_value() got unexpected positional arguments: %r" % (args,)
            )

    passed = bool(value == exp)
    _emit(
        passed,
        value,
        exp,
        alert_level,
        msg,
        scope,
        msg_id,
        radix,
        match_strictness,
        extras=extras or None,
    )
    return passed


def check_value_in_range(
    value: Any,
    min_value: Any,
    max_value: Any,
    *args: Any,
    alert_level: AlertLevel = AlertLevel.ERROR,
    msg: str = "",
    scope: str = "C_TB_SCOPE_DEFAULT",
    msg_id: str = "ID_POS_ACK",
    radix: Radix = Radix.DEC,
    **extras: Any,
) -> bool:
    """Check that ``min_value <= value <= max_value``.

    Keyword-only ``**extras`` is the same as for :func:`check_value`:
    any kwarg whose name does not match a named parameter lands in the
    record's :attr:`CheckRecord.extras` dict, ready to be reported by
    a YML-declared field.

    Returns True if in range, False otherwise. Raises AssertionError on
    out-of-range *_FAILURE/*_ERROR.
    """
    if args:
        raise TypeError(
            "check_value_in_range() got unexpected positional arguments: %r" % (args,)
        )

    passed = bool(min_value <= value <= max_value)
    _emit(
        passed=passed,
        value=value,
        exp=f"in [{min_value}, {max_value}]",
        alert_level=alert_level,
        msg=msg,
        scope=scope,
        msg_id=msg_id,
        radix=radix,
        match=None,
        extras=extras or None,
    )
    return passed


# --------------------------------------------------------------------------- #
# Stubs (hardware-simulation-time features have no Python equivalent here)     #
# --------------------------------------------------------------------------- #


def check_stable(*_args: Any, **_kwargs: Any) -> bool:
    raise NotImplementedError(
        "check_stable needs VHDL simulation time. "
        "Port to cocotb if you need signal stability in Python."
    )


def check_sb_completion(*_args: Any, **_kwargs: Any) -> bool:
    raise NotImplementedError(
        "Scoreboard completion is UVVM-specific; use a plain Python assertion."
    )


def await_change(*_args: Any, **_kwargs: Any) -> None:
    raise NotImplementedError(
        "await_change needs VHDL simulation time; use cocotb."
    )


def await_value(*_args: Any, **_kwargs: Any) -> None:
    raise NotImplementedError(
        "await_value needs VHDL simulation time; use cocotb."
    )

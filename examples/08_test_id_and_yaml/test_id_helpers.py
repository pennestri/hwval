"""User-supplied test_id update functions for example 08.

These show off the ``(record, sequence) -> str`` signature. A real
project would keep one or two of these in a ``test_id_helpers.py``
next to its test harness; the YAML config refers to them by dotted
path (``examples.test_id_helpers:make_test_id``).
"""

from __future__ import annotations

from hwval import CheckRecord


def make_test_id(record: CheckRecord, seq: int) -> str:
    """Stable id derived from scope, msg_id, and a 1-indexed sequence.

    Reads well in a report and in a log line:
    ``reg_walk.ID_REG0.0001``, ``reg_walk.ID_REG1.0002``, …
    """
    return f"{record.scope}.{record.msg_id}.{seq:04d}"

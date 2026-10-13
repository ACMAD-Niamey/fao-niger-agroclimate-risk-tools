"""Cooperative cancellation shared by the long-running workflows."""

from __future__ import annotations


class WorkflowCancelled(RuntimeError):
    """The caller asked a run to stop (for example the user cancelled a QGIS task)."""

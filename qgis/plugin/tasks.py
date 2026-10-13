"""Run the shared workflows off the main thread, so QGIS stays responsive.

A task wraps one function from ``agroclimate_core`` and turns its progress and
cancellation hooks into QGIS ones. The work runs in a background thread and
must not touch the QGIS project or any widget; the result is handed back on
the main thread in ``finished``.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any, Callable, Optional

from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsTask

from .agroclimate_core.cancellation import WorkflowCancelled

logger = logging.getLogger(__name__)

Work = Callable[[Callable[[float, str], None], Callable[[], bool]], Any]


class WorkflowTask(QgsTask):
    """Calls ``work(progress, is_cancelled)`` in the background."""

    # Emitted from the worker thread; Qt queues it to the receiver's (main) thread.
    progressed = pyqtSignal(float, str)

    def __init__(
        self,
        description: str,
        work: Work,
        *,
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None],
        on_cancel: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(description, QgsTask.CanCancel)
        self._work = work
        self._on_success = on_success
        self._on_error = on_error
        self._on_cancel = on_cancel
        self.result: Any = None
        self.error: Optional[Exception] = None
        self.was_cancelled = False

    def _progress(self, percent: float, message: str) -> None:
        self.setProgress(max(0.0, min(100.0, percent)))
        self.progressed.emit(float(percent), message)

    def run(self) -> bool:  # runs in the worker thread
        try:
            self.result = self._work(self._progress, self.isCanceled)
            return True
        except WorkflowCancelled:
            self.was_cancelled = True
            return False
        except Exception as exc:  # the caller shows it; the traceback goes to the log for support
            logger.error("%s failed: %s\n%s", self.description(), exc, traceback.format_exc())
            self.error = exc
            return False

    def finished(self, ok: bool) -> None:  # runs on the main thread
        if ok:
            self._on_success(self.result)
        elif self.was_cancelled or (self.error is None and self.isCanceled()):
            if self._on_cancel is not None:
                self._on_cancel()
        else:
            self._on_error(self.error or RuntimeError("The task failed."))

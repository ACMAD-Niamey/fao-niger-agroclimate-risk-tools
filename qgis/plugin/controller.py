"""Connects the panel to the workflows, the map and the optional language model.

This is the only place where a button press becomes a background task and a
finished task becomes layers and numbers. The workflow logic itself stays in
``agroclimate_core``; this class only wires it to QGIS.
"""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMessageLog,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from .agroclimate_core.acmad_download import AcmadProductNotFound
from .agroclimate_core.admin1_download import (
    ADMIN1_ATTRIBUTION,
    ADMIN1_CODE_FIELD,
    ADMIN1_NAME_FIELD,
    AdminBoundaryDownloadError,
)
from .agroclimate_core.admin_summary import summarize_by_admin, write_summary_csv, write_summary_geojson
from .agroclimate_core.exposure_download import ExposureDownloadError
from .agroclimate_core.exposure_workflow import ExposureConfig, run_exposure_preparation
from .agroclimate_core.hazard_selection import ConfigError
from .agroclimate_core.llm import (
    ConnectionReport,
    LlmError,
    LlmSettings,
    build_run_payload,
    check_connection,
    request_interpretation,
)
from .agroclimate_core.period_choices import PeriodChoices, load_period_choices
from .agroclimate_core.periods import PeriodUnavailableError
from .agroclimate_core.risk_statistics import RiskStatistics, summarize_risk_map
from .agroclimate_core.workflow import RunConfig, RunResult, WorkflowServices, default_services, run_risk_workflow
from .dock import RiskDock
from .layers import AddedLayers, add_run_to_project, group_name_for
from .settings import PluginSettings
from .styles import RISK_CLASS_STYLE, class_colors, style_file
from .tasks import WorkflowTask

LOG_TAG = "FAO Niger Agroclimate"
logger = logging.getLogger(__name__)


class MessageLogHandler(logging.Handler):
    """Sends the core package's log lines to QGIS's Log Messages panel."""

    _LEVELS = {logging.ERROR: Qgis.Critical, logging.WARNING: Qgis.Warning}

    def emit(self, record: logging.LogRecord) -> None:
        level = Qgis.Critical if record.levelno >= logging.ERROR else Qgis.Warning if record.levelno >= logging.WARNING else Qgis.Info
        QgsMessageLog.logMessage(self.format(record), LOG_TAG, level)


class Prompter:
    """Questions to the user. Replaced in tests so no dialog opens."""

    def __init__(self, parent=None) -> None:
        self._parent = parent

    def confirm(self, title: str, text: str) -> bool:
        return QMessageBox.question(self._parent, title, text) == QMessageBox.Yes

    def warn(self, title: str, text: str) -> None:
        QMessageBox.warning(self._parent, title, text)

    def choose_exposure_action(self, from_acmad: bool = False) -> str:
        """What to do when no exposure rasters exist: ``prepare``, ``test`` or ``cancel``.

        Offering the next step as a button, rather than a Yes/No question that tells the user to
        go and find one, is what makes the first run work without reading any documentation.
        """

        box = QMessageBox(self._parent)
        box.setWindowTitle("Exposure data needed")
        box.setText("The risk map needs exposure data, which says where there is cropland and rangeland. None was found in the exposure folder.")
        if from_acmad:
            how = (
                "Prepare it now: it downloads four small files that ACMAD has already prepared (a few seconds), "
                "and the run then continues by itself."
            )
        else:
            how = (
                "Prepare it now: it downloads land cover for Niger and builds the files (about 430 MB the first "
                "time, around 5 minutes), and the run then continues by itself. You only do this once."
            )
        box.setInformativeText(f"{how}\n\nOr run now with constant placeholder exposure. That result is only a test.")
        prepare = box.addButton("Prepare exposure, then run", QMessageBox.AcceptRole)
        test = box.addButton("Run as a test anyway", QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(prepare)
        box.exec_()
        clicked = box.clickedButton()
        return "prepare" if clicked is prepare else "test" if clicked is test else "cancel"


def _default_submit(task: WorkflowTask) -> None:
    QgsApplication.taskManager().addTask(task)


def _ignore_after_dispose(method):
    """Skip a task callback that arrives after the panel has been closed.

    A background task can finish after the user disabled the plugin; touching the
    deleted panel then crashes QGIS, so late results are dropped instead.
    """

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if self._disposed:
            return None
        return method(self, *args, **kwargs)

    return wrapper


def plain_error(exc: Exception) -> str:
    """A message a field user can act on, without a traceback."""

    if isinstance(exc, (ConfigError, PeriodUnavailableError)):
        return str(exc)
    if isinstance(exc, AcmadProductNotFound):
        return f"ACMAD has no data for this period: {exc}"
    if isinstance(exc, LlmError):
        return str(exc)
    if isinstance(exc, AdminBoundaryDownloadError):
        return f"{exc} Untick \"Use ACMAD's admin level 1 regions\" to summarise by a polygon layer of your own instead."
    if isinstance(exc, ExposureDownloadError):
        return f"{exc} Untick \"Use ACMAD's prepared exposure\" to build it from land cover instead."
    return f"{type(exc).__name__}: {exc}. See the Log Messages panel (tab '{LOG_TAG}') for details."


class RiskPanelController:
    def __init__(
        self,
        iface,
        plugin_dir: Path,
        *,
        services: Optional[WorkflowServices] = None,
        settings: Optional[PluginSettings] = None,
        submit_task: Callable[[WorkflowTask], None] = _default_submit,
        prompter: Optional[Prompter] = None,
        llm_request: Callable[..., str] = request_interpretation,
        llm_check: Callable[[LlmSettings], ConnectionReport] = check_connection,
    ) -> None:
        self.iface = iface
        self.styles_dir = Path(plugin_dir) / "styles"
        self.services = services
        self.settings = settings or PluginSettings()
        self._submit = submit_task
        self.prompter = prompter or Prompter(iface.mainWindow() if iface is not None else None)
        self._llm_request = llm_request
        self._llm_check = llm_check
        self.result: Optional[RunResult] = None
        self.stats: Optional[RiskStatistics] = None
        self.region_rows: List[Dict[str, Any]] = []
        self._task: Optional[WorkflowTask] = None
        self._period_task: Optional[WorkflowTask] = None
        self._disposed = False
        self._run_after_exposure = False  # set when the user chose "prepare exposure, then run"

        self._log_handler = MessageLogHandler()
        self._log_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        logging.getLogger("agroclimate_core").addHandler(self._log_handler)
        logging.getLogger("agroclimate_core").setLevel(logging.INFO)

        self.dock = RiskDock(iface.mainWindow() if iface is not None else None)
        self.dock.load_saved_options(
            output_root=self.settings.output_root,
            exposure_dir=self.settings.exposure_dir,
            strict=self.settings.strict_dates,
            fallback=self.settings.max_fallback_dekads,
            llm=self.settings.load_llm(),
            key_remembered=self.settings.llm_key_is_remembered,
            use_acmad_exposure=self.settings.use_acmad_exposure,
            use_acmad_regions=self.settings.use_acmad_regions,
        )
        self.dock.runRequested.connect(self.on_run_requested)
        self.dock.prepareExposureRequested.connect(self.on_prepare_exposure_requested)
        self.dock.cancelRequested.connect(self.on_cancel_requested)
        self.dock.summariseRegionsRequested.connect(self.on_summarise_regions)
        self.dock.summariseAcmadRegionsRequested.connect(self.on_summarise_acmad_regions)
        self.dock.interpretRequested.connect(self.on_interpret_requested)
        self.dock.openFolderRequested.connect(self.on_open_folder)
        self.dock.refreshPeriodsRequested.connect(self.refresh_periods)
        self.dock.saveLlmRequested.connect(self.on_save_llm)
        self.dock.testLlmRequested.connect(self.on_test_llm)

    def dispose(self) -> None:
        """Close down: stop outstanding work and ignore anything that finishes later."""

        self._disposed = True
        for task in (self._task, self._period_task):
            if task is not None:
                task.cancel()
        logging.getLogger("agroclimate_core").removeHandler(self._log_handler)
        self.dock.deleteLater()

    # ------------------------------------------------------------------- helpers
    def _message(self, text: str, level=Qgis.Info, duration: int = 8) -> None:
        if self.iface is not None:
            self.iface.messageBar().pushMessage(LOG_TAG, text, level=level, duration=duration)

    def _start(self, description: str, work: Callable, on_success: Callable[[Any], None]) -> None:
        task = WorkflowTask(description, work, on_success=on_success, on_error=self._on_failure, on_cancel=self._on_cancelled)
        task.progressed.connect(self.dock.set_progress)
        self._task = task  # a reference must be kept, or the task is garbage-collected mid-run
        self.dock.set_running(True, f"{description}...")
        self._submit(task)

    @_ignore_after_dispose
    def _on_failure(self, exc: Exception) -> None:
        self._run_after_exposure = False  # a failed preparation must not start the run
        text = plain_error(exc)
        self.dock.set_running(False, f"Failed: {text}")
        self.dock.append_log(f"Failed: {text}")
        self._message(text, Qgis.Critical, duration=0)

    @_ignore_after_dispose
    def _on_cancelled(self) -> None:
        self._run_after_exposure = False
        self.dock.set_running(False, "Cancelled.")
        self._message("The run was cancelled.", Qgis.Warning)

    def on_cancel_requested(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self.dock.status_label.setText("Cancelling...")

    # ------------------------------------------------------------------- periods
    def refresh_periods(self) -> None:
        """Ask ACMAD which periods are published and offer them in the panel.

        Runs in the background; if ACMAD cannot be reached the panel keeps a free
        date box, so being offline never blocks a run.
        """

        api_url = RunConfig().acmad_api_base_url
        task = WorkflowTask(
            "Reading ACMAD's published periods",
            lambda _progress, _cancelled: load_period_choices(self.services, api_base_url=api_url),
            on_success=self._on_periods_loaded,
            on_error=self._on_periods_failed,
            on_cancel=self.dock.finish_periods_loading,
        )
        self._period_task = task
        self.dock.set_periods_loading()
        self._submit(task)

    @_ignore_after_dispose
    def _on_periods_loaded(self, choices: PeriodChoices) -> None:
        self.dock.finish_periods_loading()
        self.dock.set_period_choices(choices)

    @_ignore_after_dispose
    def _on_periods_failed(self, exc: Exception) -> None:
        self.dock.finish_periods_loading()
        self.dock.set_period_choices(PeriodChoices(problems=("Could not reach ACMAD to list the published periods.",)))
        logger.warning("Listing published periods failed: %s", exc)

    # ----------------------------------------------------------------- risk run
    def on_run_requested(self, config: RunConfig) -> None:
        try:
            config.validate()
        except ConfigError as exc:
            self.prompter.warn("Cannot run", str(exc))
            return
        if config.cultivated_raster is None and config.rangeland_raster is None:
            choice = self.prompter.choose_exposure_action(self.dock.use_acmad_check.isChecked())
            if choice == "prepare":
                # The dialog already explained the download, so do not ask a second time.
                self._run_after_exposure = True
                self.on_prepare_exposure_requested(self.dock.collect_exposure_config(), confirmed=True)
                return
            if choice != "test":
                return
        self.settings.output_root = config.output_root
        self.settings.strict_dates = config.strict_dates
        self.settings.max_fallback_dekads = config.max_fallback_dekads
        self._start(
            "Building the risk map",
            lambda progress, cancelled: run_risk_workflow(config, services=self.services, progress=progress, is_cancelled=cancelled),
            self._on_run_succeeded,
        )

    @_ignore_after_dispose
    def _on_run_succeeded(self, result: RunResult) -> None:
        self.dock.set_running(False, "Done.")
        self.result = result
        self.region_rows = []
        try:
            added = add_run_to_project(result, QgsProject.instance(), self.styles_dir, canvas=self.iface.mapCanvas() if self.iface else None)
            self.stats = summarize_risk_map(result.outputs["risk_class"], result.outputs["risk_score"])
        except Exception as exc:  # the files exist even if showing them failed
            self._on_failure(exc)
            return
        colours = {value: colour for value, (_label, colour) in class_colors(style_file(self.styles_dir, RISK_CLASS_STYLE)).items()}
        self.dock.show_results(result, self.stats, colours)
        self.dock.refresh_llm_availability(self.settings.load_llm())
        for warning in added.warnings:
            self.dock.append_log(f"Warning: {warning}")
        level = Qgis.Warning if result.fallback or added.warnings else Qgis.Success
        suffix = " (the latest published period; the requested one is not available yet)" if result.fallback else ""
        self._message(f"Added '{group_name_for(result)}' to the map{suffix}.", level)

    # ------------------------------------------------------------------ exposure
    def on_prepare_exposure_requested(self, config: ExposureConfig, confirmed: bool = False) -> None:
        # ACMAD's prepared files are about 66 KB, so only the land cover build needs a confirmation.
        if config.source == "worldcover" and not confirmed and not self.prompter.confirm(
            "Prepare exposure",
            "This downloads ESA WorldCover land cover for Niger (about 430 MB the first time) and takes around 5 "
            "minutes. It only needs doing once. Continue?",
        ):
            return
        self.settings.exposure_dir = config.output_dir
        self.settings.use_acmad_exposure = config.source == "acmad"
        self._start(
            "Getting exposure from ACMAD" if config.source == "acmad" else "Preparing exposure from land cover",
            lambda progress, cancelled: run_exposure_preparation(config, services=self.services, progress=progress, is_cancelled=cancelled),
            lambda outputs: self._on_exposure_ready(config, outputs),
        )

    @_ignore_after_dispose
    def _on_exposure_ready(self, config: ExposureConfig, outputs: Dict[str, Path]) -> None:
        self.dock.set_running(False, "Exposure rasters are ready.")
        self.dock.exposure_widget.setFilePath(str(config.output_dir))
        self.dock.refresh_exposure_status()
        self._message(f"Exposure rasters written to {config.output_dir}.", Qgis.Success)
        if self._run_after_exposure:
            self._run_after_exposure = False
            # Re-read the panel: it now finds the new rasters, so this run is a real one, not a test.
            self.on_run_requested(self.dock.collect_run_config())

    # ------------------------------------------------------------ region summary
    def _export_region_layer(self, layer: QgsVectorLayer, target: Path) -> Path:
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GeoJSON"
        options.ct = QgsCoordinateTransform(layer.crs(), QgsCoordinateReferenceSystem("EPSG:4326"), QgsProject.instance())
        outcome = QgsVectorFileWriter.writeAsVectorFormatV3(layer, str(target), QgsProject.instance().transformContext(), options)
        if outcome[0] != QgsVectorFileWriter.NoError:
            raise RuntimeError(f"Could not read the region layer: {outcome[1]}")
        return target

    def _summarise_file(self, result: RunResult, admin_file: Path, name_field: str, code_field: Optional[str]):
        """Summarise a finished run by the regions in ``admin_file``.

        Uses only the shared core (no QGIS objects), so it is safe to call from a background task.
        """

        exposure_dir = self.settings.exposure_dir

        def optional(name: str) -> Optional[Path]:
            path = exposure_dir / name
            return path if path.is_file() else None

        rows = summarize_by_admin(
            result.outputs["risk_class"],
            result.outputs["risk_score"],
            admin_file,
            name_field=name_field,
            code_field=code_field or None,
            cultivated_fraction_path=optional("cultivated_fraction.tif"),
            rangeland_fraction_path=optional("rangeland_fraction.tif"),
        )
        write_summary_csv(rows, result.output_dir / "admin_risk_summary.csv")
        joined = write_summary_geojson(admin_file, rows, result.output_dir / "admin_risk_summary.geojson", key_field=name_field)
        return rows, joined

    def _show_regions(self, rows: List[Dict[str, Any]], joined: Path, credit: str = "") -> None:
        """Main thread: fill the table and put the joined regions on the map."""

        self.region_rows = rows
        self.dock.show_regions(rows)
        region_layer = QgsVectorLayer(str(joined), f"Risk by region ({self.result.hazard_label})", "ogr")
        group = QgsProject.instance().layerTreeRoot().findGroup(group_name_for(self.result))
        if region_layer.isValid():
            QgsProject.instance().addMapLayer(region_layer, group is None)
            if group is not None:
                group.addLayer(region_layer)
        self._message(f"Summarised {len(rows)} regions. Files are in {self.result.output_dir}. {credit}".strip(), Qgis.Success)

    def on_summarise_regions(self, layer: QgsVectorLayer, name_field: str, code_field: str) -> None:
        """Summarise by a polygon layer the user chose."""

        if self.result is None:
            self.prompter.warn("No map yet", "Run a map first.")
            return
        if not name_field:
            self.prompter.warn("Choose a name field", "Pick the field that holds each region's name.")
            return
        self.settings.use_acmad_regions = False
        try:
            admin_file = self._export_region_layer(layer, self.result.output_dir / "admin_regions.geojson")
            rows, joined = self._summarise_file(self.result, admin_file, name_field, code_field)
        except Exception as exc:
            self._on_failure(exc)
            return
        self._show_regions(rows, joined)

    def on_summarise_acmad_regions(self) -> None:
        """Summarise by ACMAD's admin level 1 regions: fetched and summarised in the background."""

        if self.result is None:
            self.prompter.warn("No map yet", "Run a map first.")
            return
        self.settings.use_acmad_regions = True
        result = self.result
        services = self.services or default_services()
        boundaries_dir = result.output_dir.parent / "boundaries"  # beside the runs, reused by later ones

        def work(_progress, cancelled):
            admin_file = services.download_admin1(boundaries_dir, is_cancelled=cancelled)
            return self._summarise_file(result, admin_file, ADMIN1_NAME_FIELD, ADMIN1_CODE_FIELD)

        self._start("Summarising by ACMAD's regions", work, self._on_acmad_regions_ready)

    @_ignore_after_dispose
    def _on_acmad_regions_ready(self, summary) -> None:
        rows, joined = summary
        self.dock.set_running(False, "Region summary ready.")
        self._show_regions(rows, joined, ADMIN1_ATTRIBUTION)

    # --------------------------------------------------------- language model
    def on_save_llm(self, llm: LlmSettings, remember: bool) -> None:
        self.settings.save_llm(llm, remember_key=remember)
        self.dock.refresh_llm_availability(self.settings.load_llm())
        self._message("Language model settings saved.", Qgis.Success, duration=4)

    def on_test_llm(self, llm: LlmSettings) -> None:
        """Check address, key and model with what is typed in the Settings tab (saved or not)."""

        self.dock.llm_test_result.setText("Testing...")
        self.dock.llm_test_result.setStyleSheet("")
        self._start(
            "Testing the language model connection",
            lambda _progress, _cancelled: self._llm_check(llm),
            self._on_llm_tested,
        )

    @_ignore_after_dispose
    def _on_llm_tested(self, report: ConnectionReport) -> None:
        self.dock.set_running(False, "Connection test finished.")
        self.dock.show_llm_test_result(report.ok, report.summary)

    def on_interpret_requested(self) -> None:
        llm = self.settings.load_llm()
        if not llm.is_configured:
            self.prompter.warn("Language model not set up", "Add the service address, key and model in the Settings tab.")
            return
        if self.result is None or self.stats is None:
            self.prompter.warn("No map yet", "Run a map first.")
            return
        host = urlparse(llm.base_url).netloc or llm.base_url
        if not self.prompter.confirm(
            "Send summary to the language model",
            f"The summary figures from the Results tab (period, class shares and the region table, if you made one) "
            f"will be sent to {host}. No rasters, file paths or personal details are sent.\n\nContinue?",
        ):
            return
        payload = build_run_payload(
            period=self.result.hazard_label,
            hazard=self.result.hazard_name,
            fallback=self.result.fallback,
            mask_applied=self.result.mask_applied,
            statistics=self.stats.as_dict(),
            regions=self.region_rows,
        )
        self._start(
            "Asking the language model",
            lambda _progress, _cancelled: self._llm_request(llm, payload),
            self._on_interpretation_ready,
        )

    @_ignore_after_dispose
    def _on_interpretation_ready(self, text: str) -> None:
        self.dock.set_running(False, "Description ready.")
        self.dock.show_interpretation(text)

    # ------------------------------------------------------------------ folder
    def on_open_folder(self) -> None:
        if self.result is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.result.output_dir)))

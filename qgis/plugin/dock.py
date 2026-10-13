"""The plugin's panel: presentation only.

The dock builds the widgets, reads them into ``RunConfig``/``ExposureConfig``
and shows results. It runs nothing itself; it emits signals and the controller
decides what to do. That keeps the workflow testable without a window.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from qgis.PyQt.QtCore import QDate, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDockWidget,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsFieldComboBox, QgsFileWidget, QgsMapLayerComboBox

from .agroclimate_core.exposure_workflow import CULTIVATED_SCORE_FILE, RANGELAND_SCORE_FILE, ExposureConfig
from .agroclimate_core.llm import LlmSettings
from .agroclimate_core.period_choices import PeriodChoices
from .agroclimate_core.risk_statistics import RiskStatistics
from .agroclimate_core.workflow import RunConfig, RunResult
from .widgets import ClassBarChart

OTHER_DATE = "other"
MAX_LOG_LINES = 300
REGION_COLUMNS = (
    ("Region", "admin_name"),
    ("Scored area (km²)", "scored_area_km2"),
    ("Mean score", "mean_risk_score"),
    ("Worst class", "max_risk_class"),
    ("High + very high (%)", None),  # computed from two columns
    ("Cropland in high risk (ha)", "cultivated_ha_high_risk"),
    ("Rangeland in high risk (ha)", "rangeland_ha_high_risk"),
)


def _directory_widget(path: Path) -> QgsFileWidget:
    widget = QgsFileWidget()
    widget.setStorageMode(QgsFileWidget.GetDirectory)
    widget.setFilePath(str(path))
    return widget


class RiskDock(QDockWidget):
    """Tabs: Run, Results, Settings."""

    runRequested = pyqtSignal(object)  # RunConfig
    prepareExposureRequested = pyqtSignal(object)  # ExposureConfig
    cancelRequested = pyqtSignal()
    summariseRegionsRequested = pyqtSignal(object, str, str)  # layer, name field, code field
    interpretRequested = pyqtSignal()
    openFolderRequested = pyqtSignal()
    refreshPeriodsRequested = pyqtSignal()
    saveLlmRequested = pyqtSignal(object, bool)  # LlmSettings, remember key

    def __init__(self, parent=None) -> None:
        super().__init__("FAO Niger Agroclimate Risk", parent)
        self.setObjectName("FaoNigerAgroclimateDock")
        self._choices = PeriodChoices()
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_run_tab(), "Run")
        self._tabs.addTab(self._build_results_tab(), "Results")
        self._tabs.addTab(self._build_settings_tab(), "Settings")
        self.setWidget(self._tabs)

    # ------------------------------------------------------------------ Run tab
    def _build_run_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        what = QGroupBox("What to map")
        form = QFormLayout(what)
        self.current_radio = QRadioButton("Current conditions (drought indicator, CDI)")
        self.outlook_radio = QRadioButton("Seasonal outlook (combined monitoring and forecast hazard)")
        self.current_radio.setChecked(True)
        self.period_combo = QComboBox()
        self.period_combo.setToolTip(
            "The periods ACMAD has published, latest first. The latest is the default. "
            "Choose 'Other date' to type a date yourself, for example when you are offline."
        )
        self.refresh_periods_button = QPushButton("Refresh")
        self.refresh_periods_button.setToolTip("Ask ACMAD which periods are published now.")
        period_row = QHBoxLayout()
        period_row.addWidget(self.period_combo, 1)
        period_row.addWidget(self.refresh_periods_button)
        self.period_status = QLabel()
        self.period_status.setWordWrap(True)
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setToolTip(
            "ACMAD publishes about a month behind. If this date is not published yet, the latest "
            "earlier period is used, and the Results tab says which."
        )
        form.addRow(self.current_radio)
        form.addRow(self.outlook_radio)
        form.addRow("Period", period_row)
        form.addRow(self.period_status)
        form.addRow("Date", self.date_edit)
        self._date_label = form.labelForField(self.date_edit)
        layout.addWidget(what)
        self.outlook_radio.toggled.connect(self._rebuild_period_combo)
        self.period_combo.currentIndexChanged.connect(self._sync_date_visibility)
        self.refresh_periods_button.clicked.connect(self.refreshPeriodsRequested.emit)

        exposure = QGroupBox("Exposure (cropland and rangeland)")
        exposure_layout = QVBoxLayout(exposure)
        self.exposure_widget = _directory_widget(Path.home())
        self.exposure_status = QLabel()
        self.exposure_status.setWordWrap(True)
        self.prepare_button = QPushButton("Prepare from land cover (about 5 minutes, needs internet)")
        self.mask_check = QCheckBox("Map only cropland and rangeland (recommended)")
        self.mask_check.setChecked(True)
        self.mask_check.setToolTip("Cells with no cropland or rangeland are left blank instead of being scored low.")
        exposure_layout.addWidget(QLabel("Folder with the prepared exposure rasters"))
        exposure_layout.addWidget(self.exposure_widget)
        exposure_layout.addWidget(self.exposure_status)
        exposure_layout.addWidget(self.prepare_button)
        exposure_layout.addWidget(self.mask_check)
        layout.addWidget(exposure)
        self.exposure_widget.fileChanged.connect(lambda _path: self.refresh_exposure_status())
        self.prepare_button.clicked.connect(self._emit_prepare)

        output = QGroupBox("Output folder")
        output_layout = QVBoxLayout(output)
        self.output_widget = _directory_widget(Path.home())
        output_layout.addWidget(self.output_widget)
        layout.addWidget(output)

        advanced = QGroupBox("Advanced")
        advanced.setCheckable(True)
        advanced.setChecked(False)
        advanced_form = QFormLayout(advanced)
        self.strict_check = QCheckBox("Do not use an earlier period if the requested one is missing")
        self.fallback_spin = QSpinBox()
        self.fallback_spin.setRange(0, 12)
        self.fallback_spin.setValue(3)
        self.fallback_spin.setToolTip("How many ten-day periods older than requested may be used.")
        advanced_form.addRow(self.strict_check)
        advanced_form.addRow("Maximum fallback (ten-day periods)", self.fallback_spin)
        layout.addWidget(advanced)

        buttons = QHBoxLayout()
        self.run_button = QPushButton("Run and add to map")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        self.run_button.clicked.connect(self._emit_run)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.status_label = QLabel("Ready.")
        self.status_label.setWordWrap(True)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(MAX_LOG_LINES)
        self.log_view.setMaximumHeight(110)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.log_view)
        layout.addStretch(1)
        self._rebuild_period_combo()
        return page

    # ------------------------------------------------------------------ periods
    def set_period_choices(self, choices: PeriodChoices) -> None:
        """Fill the period list from what ACMAD has published."""

        self._choices = choices
        self._rebuild_period_combo()
        if choices.problems:
            self.period_status.setText(" ".join(choices.problems) + " You can still choose 'Other date' and type one.")
        else:
            self.period_status.setText("Periods published by ACMAD, latest first. The latest is selected.")

    def set_periods_loading(self) -> None:
        self.refresh_periods_button.setEnabled(False)
        self.period_status.setText("Asking ACMAD which periods are published...")

    def finish_periods_loading(self) -> None:
        self.refresh_periods_button.setEnabled(True)

    def _rebuild_period_combo(self, *_args: Any) -> None:
        outlook = self.outlook_radio.isChecked()
        periods = list(self._choices.seasons if outlook else self._choices.dekads)
        self.period_combo.blockSignals(True)
        self.period_combo.clear()
        for index, period in enumerate(periods):
            label = f"Latest available ({period.label if not outlook else period.text})" if index == 0 else (
                period.text if outlook else period.label
            )
            data = ("season", period.year, period.label) if outlook else ("dekad", period.year, period.month, period.dekad)
            self.period_combo.addItem(label, data)
        self.period_combo.addItem("Other date...", (OTHER_DATE,))
        self.period_combo.setCurrentIndex(0)  # the latest published period, or 'Other date' when none is known
        self.period_combo.blockSignals(False)
        self._sync_date_visibility()

    def _sync_date_visibility(self, *_args: Any) -> None:
        """Show the date box only for 'Other date': next to a published period it is just noise."""

        data = self.period_combo.currentData()
        typing_a_date = bool(data) and data[0] == OTHER_DATE
        self.date_edit.setEnabled(typing_a_date)
        self.date_edit.setVisible(typing_a_date)
        self._date_label.setVisible(typing_a_date)

    # --------------------------------------------------------------- results tab
    def _build_results_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.result_header = QLabel("Run a map to see its results here.")
        self.result_header.setWordWrap(True)
        self.result_header.setTextFormat(Qt.RichText)
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #8a4b00;")
        self.warning_label.hide()
        layout.addWidget(self.result_header)
        layout.addWidget(self.warning_label)

        self.chart = ClassBarChart()
        layout.addWidget(self.chart)
        self.class_table = QTableWidget(0, 3)
        self.class_table.setHorizontalHeaderLabels(["Risk class", "Area (km²)", "Share of scored area"])
        self.class_table.verticalHeader().hide()
        self.class_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.class_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.class_table.setMaximumHeight(150)
        layout.addWidget(self.class_table)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        regions = QGroupBox("Summary by region")
        regions_layout = QVBoxLayout(regions)
        regions_layout.addWidget(QLabel("Polygon layer with the regions (for example admin level 1)"))
        self.region_layer_combo = QgsMapLayerComboBox()
        self.region_layer_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.region_layer_combo.setAllowEmptyLayer(True)
        self.region_name_combo = QgsFieldComboBox()
        self.region_code_combo = QgsFieldComboBox()
        self.region_code_combo.setAllowEmptyFieldName(True)
        self.region_layer_combo.layerChanged.connect(self.region_name_combo.setLayer)
        self.region_layer_combo.layerChanged.connect(self.region_code_combo.setLayer)
        form = QFormLayout()
        form.addRow("Name field", self.region_name_combo)
        form.addRow("Code field (optional)", self.region_code_combo)
        regions_layout.addLayout(form)
        self.summarise_button = QPushButton("Summarise by region")
        self.summarise_button.setEnabled(False)
        regions_layout.addWidget(self.summarise_button)
        self.region_table = QTableWidget(0, len(REGION_COLUMNS))
        self.region_table.setHorizontalHeaderLabels([title for title, _ in REGION_COLUMNS])
        self.region_table.verticalHeader().hide()
        self.region_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.region_table.setSortingEnabled(True)
        self.region_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        regions_layout.addWidget(self.region_table)
        layout.addWidget(regions)
        self.summarise_button.clicked.connect(self._emit_summarise)

        interpretation = QGroupBox("Plain-language description (optional)")
        interpretation_layout = QVBoxLayout(interpretation)
        self.interpret_button = QPushButton("Describe with the language model")
        self.interpret_button.setEnabled(False)
        self.interpret_note = QLabel()
        self.interpret_note.setWordWrap(True)
        self.interpretation_view = QTextEdit()
        self.interpretation_view.setReadOnly(True)
        self.interpretation_view.setMaximumHeight(160)
        interpretation_layout.addWidget(self.interpret_button)
        interpretation_layout.addWidget(self.interpret_note)
        interpretation_layout.addWidget(self.interpretation_view)
        layout.addWidget(interpretation)
        self.interpret_button.clicked.connect(self.interpretRequested.emit)

        self.open_folder_button = QPushButton("Open results folder")
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.clicked.connect(self.openFolderRequested.emit)
        layout.addWidget(self.open_folder_button)
        layout.addStretch(1)
        return page

    # -------------------------------------------------------------- settings tab
    def _build_settings_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox("Language model (optional)")
        form = QFormLayout(group)
        self.llm_url = QLineEdit()
        self.llm_url.setPlaceholderText("https://your-service.example.org/v1")
        self.llm_model = QLineEdit()
        self.llm_key = QLineEdit()
        self.llm_key.setEchoMode(QLineEdit.Password)
        self.llm_language = QComboBox()
        self.llm_language.addItem("English", "en")
        self.llm_language.addItem("Français", "fr")
        self.llm_remember = QCheckBox("Remember the key in my QGIS profile (stored unencrypted)")
        form.addRow("Service address", self.llm_url)
        form.addRow("Model", self.llm_model)
        form.addRow("API key", self.llm_key)
        form.addRow("Language", self.llm_language)
        form.addRow(self.llm_remember)
        layout.addWidget(group)
        note = QLabel(
            "The risk maps and statistics work without a language model. If you set one up, only the summary "
            "figures shown in the Results tab are sent, never the rasters or file paths, and every description is "
            "marked as a draft for expert review. Any service that speaks the OpenAI-style chat protocol works."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.save_llm_button = QPushButton("Save")
        layout.addWidget(self.save_llm_button)
        self.save_llm_button.clicked.connect(self._emit_save_llm)
        layout.addStretch(1)
        return page

    # ----------------------------------------------------------- reading widgets
    def collect_run_config(self) -> RunConfig:
        outlook = self.outlook_radio.isChecked()
        data = self.period_combo.currentData() or (OTHER_DATE,)
        qdate = self.date_edit.date()
        cultivated, rangeland = self._exposure_files()
        fields = dict(
            output_root=Path(self.output_widget.filePath()),
            hazard="combined" if outlook else "cdi",
            max_fallback_dekads=self.fallback_spin.value(),
            strict_dates=self.strict_check.isChecked(),
            cultivated_raster=cultivated,
            rangeland_raster=rangeland,
            mask_to_agropastoral=None if self.mask_check.isChecked() else False,
        )
        if data[0] == "dekad":  # a published period picked from the list is exact
            return RunConfig(year=data[1], month=data[2], dekad=data[3], **fields)
        if data[0] == "season":
            return RunConfig(forecast_year=data[1], forecast_period=data[2], **fields)
        return RunConfig(analysis_date=date(qdate.year(), qdate.month(), qdate.day()), **fields)

    def collect_exposure_config(self) -> ExposureConfig:
        output_dir = Path(self.exposure_widget.filePath())
        return ExposureConfig(output_dir=output_dir, cache_dir=output_dir.parent / "cache" / "worldcover")

    def collect_llm_settings(self) -> LlmSettings:
        return LlmSettings(
            base_url=self.llm_url.text(),
            api_key=self.llm_key.text(),
            model=self.llm_model.text(),
            language=self.llm_language.currentData() or "en",
        )

    def _exposure_files(self):
        folder = Path(self.exposure_widget.filePath())
        cultivated, rangeland = folder / CULTIVATED_SCORE_FILE, folder / RANGELAND_SCORE_FILE
        if cultivated.is_file() and rangeland.is_file():
            return cultivated, rangeland
        return None, None

    # -------------------------------------------------------------------- signals
    def _emit_run(self) -> None:
        self.runRequested.emit(self.collect_run_config())

    def _emit_prepare(self) -> None:
        self.prepareExposureRequested.emit(self.collect_exposure_config())

    def _emit_summarise(self) -> None:
        layer = self.region_layer_combo.currentLayer()
        if layer is not None:
            self.summariseRegionsRequested.emit(layer, self.region_name_combo.currentField(), self.region_code_combo.currentField())

    def _emit_save_llm(self) -> None:
        self.saveLlmRequested.emit(self.collect_llm_settings(), self.llm_remember.isChecked())

    # ------------------------------------------------------------- state from outside
    def load_saved_options(self, *, output_root: Path, exposure_dir: Path, strict: bool, fallback: int, llm: LlmSettings, key_remembered: bool) -> None:
        self.output_widget.setFilePath(str(output_root))
        self.exposure_widget.setFilePath(str(exposure_dir))
        self.strict_check.setChecked(strict)
        self.fallback_spin.setValue(fallback)
        self.llm_url.setText(llm.base_url)
        self.llm_model.setText(llm.model)
        self.llm_key.setText(llm.api_key)
        self.llm_remember.setChecked(key_remembered)
        index = self.llm_language.findData(llm.language)
        self.llm_language.setCurrentIndex(max(0, index))
        self.refresh_exposure_status()
        self.refresh_llm_availability(llm)

    def refresh_exposure_status(self) -> None:
        cultivated, _ = self._exposure_files()
        if cultivated is not None:
            self.exposure_status.setText("Exposure rasters found. Runs will map only cropland and rangeland.")
        else:
            self.exposure_status.setText(
                "No exposure rasters in this folder. Prepare them once from land cover, or point to a folder that has "
                f"{CULTIVATED_SCORE_FILE} and {RANGELAND_SCORE_FILE}."
            )

    def refresh_llm_availability(self, llm: LlmSettings) -> None:
        self.interpret_button.setEnabled(llm.is_configured and getattr(self, "_has_result", False))
        self.interpret_note.setText(
            "" if llm.is_configured else "Set the service address, key and model in the Settings tab to enable this."
        )

    def set_running(self, running: bool, status: Optional[str] = None) -> None:
        self.run_button.setEnabled(not running)
        self.prepare_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        if status is not None:
            self.status_label.setText(status)
        if not running:
            self.progress_bar.setValue(0)

    def set_progress(self, percent: float, message: str) -> None:
        self.progress_bar.setValue(int(percent))
        self.status_label.setText(message)
        self.append_log(f"{percent:3.0f}%  {message}")

    def append_log(self, line: str) -> None:
        self.log_view.appendPlainText(line)

    # ------------------------------------------------------------------- show results
    def show_results(self, result: RunResult, stats: RiskStatistics, colours: Dict[int, str]) -> None:
        self._has_result = True
        self.result_header.setText(
            f"<b>{result.hazard_label}</b> &nbsp; ({'seasonal outlook' if result.hazard_name == 'combined_hazard' else 'current CDI'})"
        )
        notes = list(result.warnings)
        if not result.mask_applied:
            notes.append("No cropland and rangeland mask was applied, so every cell is scored. Treat this as a test.")
        self.warning_label.setText("\n".join(notes))
        self.warning_label.setVisible(bool(notes))

        self.chart.set_bars([(c.name.capitalize(), c.share_pct, colours.get(c.value, "#999999")) for c in stats.classes])
        self.class_table.setRowCount(len(stats.classes))
        for row, cls in enumerate(stats.classes):
            for column, text in enumerate((cls.name.capitalize(), f"{cls.area_km2:,.0f}", f"{cls.share_pct:.1f}%")):
                self.class_table.setItem(row, column, QTableWidgetItem(text))
        mean = "n/a" if stats.mean_risk_score is None else f"{stats.mean_risk_score:.2f} of 3"
        self.summary_label.setText(
            f"Scored area: {stats.scored_area_km2:,.0f} km² ({stats.scored_cells:,} of {stats.total_cells:,} cells). "
            f"Mean score {mean}. Worst class present: {stats.worst_class}."
        )
        self.summarise_button.setEnabled(True)
        self.open_folder_button.setEnabled(True)
        self.interpretation_view.clear()
        self._tabs.setCurrentIndex(1)

    def show_regions(self, rows: List[Dict[str, Any]]) -> None:
        self.region_table.setSortingEnabled(False)
        self.region_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column, (_title, key) in enumerate(REGION_COLUMNS):
                if key is None:
                    high = (row.get("pct_high") or 0) + (row.get("pct_very_high") or 0)
                    text = "n/a" if row.get("pct_high") is None else f"{high:.1f}"
                else:
                    value = row.get(key)
                    text = "n/a" if value is None else (f"{value:,.1f}" if isinstance(value, float) else str(value))
                self.region_table.setItem(row_index, column, QTableWidgetItem(text))
        self.region_table.setSortingEnabled(True)

    def show_interpretation(self, text: str) -> None:
        self.interpretation_view.setPlainText(text)

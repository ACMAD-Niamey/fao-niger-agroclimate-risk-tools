"""QGIS Processing wrapper for the Agropastoral Drought Risk Map.

This script is intended to be added to the QGIS Processing Toolbox. It keeps
the geospatial wrapper separate from the tested core scoring logic in
``src/agroclimate_core`` so the same backend can later be wrapped by a
QGIS plugin.
"""

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterString,
    QgsVectorLayer,
)

try:
    from .bootstrap import ensure_src_path
except ImportError:
    from bootstrap import ensure_src_path

ensure_src_path()

from agroclimate_core.risk import (
    calculate_exposure_score,
    calculate_hazard_score,
    calculate_risk_score,
    classify_risk,
)
from agroclimate_core.acmad_boundaries import DEFAULT_ACMAD_GEOSERVER_URL, build_wfs_getfeature_url, niger_boundary_request

try:
    from .fields import OUTPUT_FIELD_DEFINITIONS
except ImportError:
    from fields import OUTPUT_FIELD_DEFINITIONS


class AgropastoralDroughtRiskAlgorithm(QgsProcessingAlgorithm):
    BOUNDARY_SOURCE = "BOUNDARY_SOURCE"
    WFS_URL = "WFS_URL"
    WORKSPACE = "WORKSPACE"
    ADMIN_LEVEL = "ADMIN_LEVEL"
    TYPE_NAME = "TYPE_NAME"
    INPUT = "INPUT"
    CDI_FIELD = "CDI_FIELD"
    FAPAR_FIELD = "FAPAR_FIELD"
    SOIL_FIELD = "SOIL_FIELD"
    CULTIVATED_FIELD = "CULTIVATED_FIELD"
    RANGELAND_FIELD = "RANGELAND_FIELD"
    WATER_FIELD = "WATER_FIELD"
    VULNERABILITY_FIELD = "VULNERABILITY_FIELD"
    OUTPUT = "OUTPUT"
    OUTPUT_FIELD_NAMES = [name for name, _field_type in OUTPUT_FIELD_DEFINITIONS]
    BOUNDARY_SOURCE_OPTIONS = [
        "Use existing QGIS vector layer",
        "Fetch Niger boundary from ACMAD WFS",
    ]
    ADMIN_LEVEL_OPTIONS = [
        "Admin level 0 - country boundary",
        "Admin level 1 - first administrative level",
    ]

    def tr(self, string):
        return QCoreApplication.translate("AgropastoralDroughtRisk", string)

    def createInstance(self):
        return AgropastoralDroughtRiskAlgorithm()

    def name(self):
        return "agropastoral_drought_risk"

    def displayName(self):
        return self.tr("Agropastoral Drought Risk Map")

    def group(self):
        return self.tr("FAO Niger Agroclimate")

    def groupId(self):
        return "fao_niger_agroclimate"

    def shortHelpString(self):
        return self.tr(
            "Calculates agropastoral drought risk from ACMAD CDI, optional fAPAR and soil moisture anomaly fields, "
            "and local exposure fields. The output adds hazard_score, exposure_score, risk_score, and risk_class. "
            "The zonal layer can be selected from QGIS or fetched from ACMAD WFS for Niger boundaries. "
            "This Processing algorithm is the backend used by the future plugin UI."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterEnum(
                self.BOUNDARY_SOURCE,
                self.tr("Zonal boundary source"),
                options=self.BOUNDARY_SOURCE_OPTIONS,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.WFS_URL,
                self.tr("ACMAD GeoServer/WFS URL, used when fetching boundary"),
                defaultValue=DEFAULT_ACMAD_GEOSERVER_URL,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.WORKSPACE,
                self.tr("GeoServer workspace (optional)"),
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.ADMIN_LEVEL,
                self.tr("ACMAD boundary admin level"),
                options=self.ADMIN_LEVEL_OPTIONS,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.TYPE_NAME,
                self.tr("Override WFS typeName/layer name, optional"),
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Input zonal layer, used when source is existing QGIS layer"),
                [QgsProcessing.TypeVectorAnyGeometry],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.CDI_FIELD,
                self.tr("CDI field"),
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.FAPAR_FIELD,
                self.tr("fAPAR anomaly field (optional)"),
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.SOIL_FIELD,
                self.tr("Soil moisture anomaly field (optional)"),
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.CULTIVATED_FIELD,
                self.tr("Cultivated exposure field"),
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.RANGELAND_FIELD,
                self.tr("Rangeland exposure field"),
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.WATER_FIELD,
                self.tr("Water-point exposure field"),
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.VULNERABILITY_FIELD,
                self.tr("Vulnerability field (optional)"),
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("Risk output")))

    def processAlgorithm(self, parameters, context, feedback):
        source, source_crs, source_wkb_type = self._resolve_source(parameters, context, feedback)

        cdi_field = self._required_field(parameters, self.CDI_FIELD, context, "CDI field")
        fapar_field = self.parameterAsString(parameters, self.FAPAR_FIELD, context)
        soil_field = self.parameterAsString(parameters, self.SOIL_FIELD, context)
        cultivated_field = self._required_field(parameters, self.CULTIVATED_FIELD, context, "cultivated exposure field")
        rangeland_field = self._required_field(parameters, self.RANGELAND_FIELD, context, "rangeland exposure field")
        water_field = self._required_field(parameters, self.WATER_FIELD, context, "water-point exposure field")
        vulnerability_field = self.parameterAsString(parameters, self.VULNERABILITY_FIELD, context)

        fields = QgsFields(source.fields())
        for field_name, field_type in OUTPUT_FIELD_DEFINITIONS:
            qvariant_type = QVariant.Double if field_type == "double" else QVariant.String
            fields.append(QgsField(field_name, qvariant_type))

        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            source_wkb_type,
            source_crs,
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        total = 100.0 / source.featureCount() if source.featureCount() else 0
        for current, feature in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break

            try:
                hazard_score = calculate_hazard_score(
                    feature[cdi_field],
                    feature[fapar_field] if fapar_field else None,
                    feature[soil_field] if soil_field else None,
                )
                exposure_score = calculate_exposure_score(
                    feature[cultivated_field],
                    feature[rangeland_field],
                    feature[water_field],
                )
                risk_score = calculate_risk_score(
                    hazard_score,
                    exposure_score,
                    feature[vulnerability_field] if vulnerability_field else None,
                )
                risk_class = classify_risk(risk_score)
            except ValueError as exc:
                raise QgsProcessingException(f"Feature {feature.id()} failed risk scoring: {exc}") from exc

            output_feature = QgsFeature(fields)
            output_feature.setGeometry(feature.geometry())
            output_feature.setAttributes(feature.attributes() + [hazard_score, exposure_score, risk_score, risk_class])
            sink.addFeature(output_feature, QgsFeatureSink.FastInsert)
            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}

    def _required_field(self, parameters, parameter_name, context, label):
        field_name = self.parameterAsString(parameters, parameter_name, context).strip()
        if not field_name:
            raise QgsProcessingException(
                f"Missing {label}. If you fetched a boundary from ACMAD WFS, it provides geometry only; "
                "join or calculate the CDI and exposure fields before running the risk score."
            )
        return field_name

    def _resolve_source(self, parameters, context, feedback):
        boundary_source = self.parameterAsEnum(parameters, self.BOUNDARY_SOURCE, context)
        if boundary_source == 0:
            source = self.parameterAsSource(parameters, self.INPUT, context)
            if source is None:
                raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
            return source, source.sourceCrs(), source.wkbType()

        wfs_url = self.parameterAsString(parameters, self.WFS_URL, context).strip()
        if not wfs_url:
            raise QgsProcessingException("ACMAD WFS URL is required when fetching the zonal boundary from ACMAD WFS")

        admin_level = self.parameterAsEnum(parameters, self.ADMIN_LEVEL, context)
        type_name = self.parameterAsString(parameters, self.TYPE_NAME, context).strip() or None
        workspace = self.parameterAsString(parameters, self.WORKSPACE, context).strip() or None
        request = niger_boundary_request(
            wfs_url=wfs_url,
            admin_level=admin_level,
            type_name=type_name,
            workspace=workspace,
        )
        getfeature_url = build_wfs_getfeature_url(request)
        feedback.pushInfo(f"Fetching zonal boundary from: {getfeature_url}")

        layer = QgsVectorLayer(getfeature_url, f"ACMAD Niger admin {admin_level}", "ogr")
        if not layer.isValid():
            raise QgsProcessingException(
                "Could not load ACMAD WFS boundary as a vector layer. Check the WFS URL, layer name, and network access."
            )
        return layer, layer.crs(), layer.wkbType()

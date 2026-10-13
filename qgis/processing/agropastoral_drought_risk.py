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
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsVectorLayer,
)

from ..agroclimate_core.risk import (
    calculate_exposure_score,
    calculate_hazard_score,
    calculate_risk_score,
    classify_risk,
)
from ..agroclimate_core.acmad_boundaries import DEFAULT_ACMAD_GEOSERVER_URL, build_wfs_getfeature_url, niger_boundary_request

from .fields import OUTPUT_FIELD_DEFINITIONS


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
    DEFAULT_CDI_SCORE = "DEFAULT_CDI_SCORE"
    DEFAULT_CULTIVATED_SCORE = "DEFAULT_CULTIVATED_SCORE"
    DEFAULT_RANGELAND_SCORE = "DEFAULT_RANGELAND_SCORE"
    DEFAULT_WATER_SCORE = "DEFAULT_WATER_SCORE"
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
        return self.tr("Score a zonal layer (vector, advanced)")

    def group(self):
        return self.tr("FAO Niger Agroclimate")

    def groupId(self):
        return "fao_niger_agroclimate"

    def shortHelpString(self):
        return self.tr(
            "ADVANCED. This scores a vector layer of zones (regions, intervention areas, a precomputed overlay) and "
            "writes a vector layer with hazard_score, exposure_score, risk_score and risk_class. It does NOT download "
            "ACMAD data and does NOT produce a raster. "
            "To build the risk MAP (rasters added to the map, styled, with statistics), use the Agroclimate Risk "
            "panel instead: toolbar icon, or Plugins > FAO Niger Agroclimate > Open Agroclimate Risk Panel. "
            "Use this algorithm only if you already have a zonal layer with CDI and exposure fields."
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
                self.tr("CDI field (optional if using default score)"),
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEFAULT_CDI_SCORE,
                self.tr("Default CDI score, used if no CDI field"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=2.0,
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
                self.tr("Cultivated exposure field (optional if using default score)"),
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEFAULT_CULTIVATED_SCORE,
                self.tr("Default cultivated exposure score, used if no field"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=2.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.RANGELAND_FIELD,
                self.tr("Rangeland exposure field (optional if using default score)"),
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEFAULT_RANGELAND_SCORE,
                self.tr("Default rangeland exposure score, used if no field"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=2.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.WATER_FIELD,
                self.tr("Water-point exposure field (optional if using default score)"),
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEFAULT_WATER_SCORE,
                self.tr("Default water-point exposure score, used if no field"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=1.0,
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

        cdi_field = self.parameterAsString(parameters, self.CDI_FIELD, context).strip()
        fapar_field = self.parameterAsString(parameters, self.FAPAR_FIELD, context)
        soil_field = self.parameterAsString(parameters, self.SOIL_FIELD, context)
        cultivated_field = self.parameterAsString(parameters, self.CULTIVATED_FIELD, context).strip()
        rangeland_field = self.parameterAsString(parameters, self.RANGELAND_FIELD, context).strip()
        water_field = self.parameterAsString(parameters, self.WATER_FIELD, context).strip()
        vulnerability_field = self.parameterAsString(parameters, self.VULNERABILITY_FIELD, context)
        default_cdi_score = self.parameterAsDouble(parameters, self.DEFAULT_CDI_SCORE, context)
        default_cultivated_score = self.parameterAsDouble(parameters, self.DEFAULT_CULTIVATED_SCORE, context)
        default_rangeland_score = self.parameterAsDouble(parameters, self.DEFAULT_RANGELAND_SCORE, context)
        default_water_score = self.parameterAsDouble(parameters, self.DEFAULT_WATER_SCORE, context)

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
                    self._field_or_default(feature, cdi_field, default_cdi_score),
                    feature[fapar_field] if fapar_field else None,
                    feature[soil_field] if soil_field else None,
                )
                exposure_score = calculate_exposure_score(
                    self._field_or_default(feature, cultivated_field, default_cultivated_score),
                    self._field_or_default(feature, rangeland_field, default_rangeland_score),
                    self._field_or_default(feature, water_field, default_water_score),
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

    def _field_or_default(self, feature, field_name, default_value):
        if not field_name:
            return default_value
        try:
            return feature[field_name]
        except KeyError as exc:
            raise QgsProcessingException(f"Field '{field_name}' was not found in the selected zonal layer.") from exc

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

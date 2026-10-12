"""QGIS Processing wrapper for the Agropastoral Drought Risk Map.

This script is intended to be added to the QGIS Processing Toolbox. It keeps
the geospatial wrapper separate from the tested core scoring logic in
``src/fao_niger_agroclimate`` so the same backend can later be wrapped by a
QGIS plugin.
"""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsWkbTypes,
)
from PyQt5.QtCore import QVariant

from fao_niger_agroclimate.risk import calculate_exposure_score, calculate_hazard_score, calculate_risk_score, classify_risk


class AgropastoralDroughtRiskAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    CDI_FIELD = "CDI_FIELD"
    FAPAR_FIELD = "FAPAR_FIELD"
    SOIL_FIELD = "SOIL_FIELD"
    CULTIVATED_FIELD = "CULTIVATED_FIELD"
    RANGELAND_FIELD = "RANGELAND_FIELD"
    WATER_FIELD = "WATER_FIELD"
    VULNERABILITY_FIELD = "VULNERABILITY_FIELD"
    OUTPUT = "OUTPUT"

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
            "and local exposure fields. The output adds hazard_score, exposure_score, risk_score, and risk_class."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT, self.tr("Input zonal layer"), [QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterField(self.CDI_FIELD, self.tr("CDI field"), parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(self.FAPAR_FIELD, self.tr("fAPAR anomaly field (optional)"), parentLayerParameterName=self.INPUT, optional=True))
        self.addParameter(QgsProcessingParameterField(self.SOIL_FIELD, self.tr("Soil moisture anomaly field (optional)"), parentLayerParameterName=self.INPUT, optional=True))
        self.addParameter(QgsProcessingParameterField(self.CULTIVATED_FIELD, self.tr("Cultivated exposure field"), parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(self.RANGELAND_FIELD, self.tr("Rangeland exposure field"), parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(self.WATER_FIELD, self.tr("Water-point exposure field"), parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(self.VULNERABILITY_FIELD, self.tr("Vulnerability field (optional)"), parentLayerParameterName=self.INPUT, optional=True))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("Risk output")))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        cdi_field = self.parameterAsString(parameters, self.CDI_FIELD, context)
        fapar_field = self.parameterAsString(parameters, self.FAPAR_FIELD, context)
        soil_field = self.parameterAsString(parameters, self.SOIL_FIELD, context)
        cultivated_field = self.parameterAsString(parameters, self.CULTIVATED_FIELD, context)
        rangeland_field = self.parameterAsString(parameters, self.RANGELAND_FIELD, context)
        water_field = self.parameterAsString(parameters, self.WATER_FIELD, context)
        vulnerability_field = self.parameterAsString(parameters, self.VULNERABILITY_FIELD, context)

        fields = QgsFields(source.fields())
        fields.append(QgsField("hazard_score", QVariant.Double))
        fields.append(QgsField("exposure_score", QVariant.Double))
        fields.append(QgsField("risk_score", QVariant.Double))
        fields.append(QgsField("risk_class", QVariant.String))

        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            source.wkbType(),
            source.sourceCrs(),
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

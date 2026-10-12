"""QGIS Processing algorithm to fetch ACMAD boundary layers from WFS."""

from __future__ import annotations

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsFeature,
    QgsFeatureSink,
    QgsFields,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterString,
    QgsVectorLayer,
)

try:
    from .bootstrap import ensure_src_path
except ImportError:
    from bootstrap import ensure_src_path

ensure_src_path()

from agroclimate_core.acmad_boundaries import DEFAULT_ACMAD_GEOSERVER_URL, build_wfs_getfeature_url, niger_boundary_request


class FetchAcmadBoundaryAlgorithm(QgsProcessingAlgorithm):
    WFS_URL = "WFS_URL"
    WORKSPACE = "WORKSPACE"
    ADMIN_LEVEL = "ADMIN_LEVEL"
    TYPE_NAME = "TYPE_NAME"
    OUTPUT = "OUTPUT"

    ADMIN_LEVEL_OPTIONS = [
        "Admin level 0 - country boundary",
        "Admin level 1 - first administrative level",
    ]

    def tr(self, string):
        return QCoreApplication.translate("FetchAcmadBoundary", string)

    def createInstance(self):
        return FetchAcmadBoundaryAlgorithm()

    def name(self):
        return "fetch_acmad_boundary"

    def displayName(self):
        return self.tr("Fetch ACMAD Boundary Layer")

    def group(self):
        return self.tr("FAO Niger Agroclimate")

    def groupId(self):
        return "fao_niger_agroclimate"

    def shortHelpString(self):
        return self.tr(
            "Fetches a Niger boundary layer from ACMAD WFS. Admin level 0 defaults to "
            "data_api_adminlevelzero with CQL_FILTER country_code=181. The output can be used as the zonal layer "
            "for downstream risk products."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterString(
                self.WFS_URL,
                self.tr("ACMAD GeoServer/WFS URL"),
                defaultValue=DEFAULT_ACMAD_GEOSERVER_URL,
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
                self.tr("Boundary admin level"),
                options=self.ADMIN_LEVEL_OPTIONS,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.TYPE_NAME,
                self.tr("Override WFS typeName/layer name (optional)"),
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("Boundary output")))

    def processAlgorithm(self, parameters, context, feedback):
        wfs_url = self.parameterAsString(parameters, self.WFS_URL, context).strip()
        if not wfs_url:
            raise QgsProcessingException("ACMAD WFS URL is required")

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
        feedback.pushInfo(f"Fetching boundary from: {getfeature_url}")

        layer = QgsVectorLayer(getfeature_url, f"ACMAD Niger admin {admin_level}", "ogr")
        if not layer.isValid():
            raise QgsProcessingException(
                "Could not load boundary response as a vector layer. Check the WFS URL, layer name, and network access."
            )

        fields = QgsFields(layer.fields())
        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            layer.wkbType(),
            layer.crs(),
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        for current, feature in enumerate(layer.getFeatures()):
            if feedback.isCanceled():
                break
            output_feature = QgsFeature(fields)
            output_feature.setGeometry(feature.geometry())
            output_feature.setAttributes(feature.attributes())
            sink.addFeature(output_feature, QgsFeatureSink.FastInsert)
            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}

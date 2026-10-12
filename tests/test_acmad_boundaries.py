import unittest
from urllib.parse import parse_qs, urlparse

from agroclimate_core.acmad_boundaries import (
    BoundaryRequest,
    boundary_request_from_country_info,
    build_wfs_getfeature_url,
    niger_boundary_request,
    normalize_wfs_url,
    qualify_type_name,
)


class AcmadBoundaryTests(unittest.TestCase):
    def test_build_wfs_getfeature_url(self):
        url = build_wfs_getfeature_url(
            BoundaryRequest(
                wfs_url="https://example.org/geoserver/ows",
                type_name="acmad:adm0",
                country_code="ner",
                country_field="iso3",
            )
        )

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(query["service"], ["WFS"])
        self.assertEqual(query["request"], ["GetFeature"])
        self.assertEqual(query["typeName"], ["acmad:adm0"])
        self.assertEqual(query["outputFormat"], ["application/json"])
        self.assertEqual(query["CQL_FILTER"], ["iso3='NER'"])

    def test_geoserver_base_url_is_normalized_to_ows(self):
        self.assertEqual(
            normalize_wfs_url("https://ada.acmad.org/geoserver"),
            "https://ada.acmad.org/geoserver/wfs",
        )
        url = build_wfs_getfeature_url(
            BoundaryRequest(
                wfs_url="https://ada.acmad.org/geoserver",
                type_name="data_api_adminlevelzero",
                country_code=181,
            )
        )
        self.assertTrue(url.startswith("https://ada.acmad.org/geoserver/wfs?"))
        self.assertIn("typeName=data_api_adminlevelzero", url)
        self.assertIn("CQL_FILTER=country_code%3D%27181%27", url)

    def test_type_name_can_be_qualified_with_workspace(self):
        self.assertEqual(
            qualify_type_name("data_api_adminlevelzero", "acmad"),
            "acmad:data_api_adminlevelzero",
        )
        self.assertEqual(
            qualify_type_name("acmad:data_api_adminlevelzero", "other"),
            "acmad:data_api_adminlevelzero",
        )

    def test_boundary_request_from_explicit_country_info(self):
        request = boundary_request_from_country_info(
            {
                "country_code": 181,
                "wfs_url": "https://example.org/geoserver/ows",
                "admin0_typename": "data_api_adminlevelzero",
                "country_field": "country_code",
            },
            admin_level=0,
        )

        self.assertEqual(request.country_code, 181)
        self.assertEqual(request.type_name, "data_api_adminlevelzero")
        self.assertEqual(request.country_field, "country_code")

    def test_boundary_request_from_layer_template(self):
        request = boundary_request_from_country_info(
            {
                "country_code": "NER",
                "geoserver_url": "https://example.org/geoserver",
                "boundary_layer_template": "acmad:{country_code}_adm{admin_level}",
            },
            admin_level=1,
        )

        self.assertEqual(request.wfs_url, "https://example.org/geoserver/wfs")
        self.assertEqual(request.type_name, "acmad:ner_adm1")

    def test_niger_boundary_request_uses_actual_country_code_and_admin0_layer(self):
        request = niger_boundary_request(
            wfs_url="https://example.org/geoserver/ows",
            admin_level=0,
        )
        url = build_wfs_getfeature_url(request)

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(request.type_name, "data_api_adminlevelzero")
        self.assertEqual(query["typeName"], ["data_api_adminlevelzero"])
        self.assertEqual(query["CQL_FILTER"], ["country_code='181'"])

    def test_niger_boundary_request_can_use_workspace(self):
        request = niger_boundary_request(
            wfs_url="https://example.org/geoserver",
            admin_level=0,
            workspace="acmad",
        )
        url = build_wfs_getfeature_url(request)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(query["typeName"], ["acmad:data_api_adminlevelzero"])


if __name__ == "__main__":
    unittest.main()

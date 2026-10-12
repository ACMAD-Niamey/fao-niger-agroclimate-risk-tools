import unittest

from agroclimate_core.acmad_availability import combined_product_seasons, latest_dekad_range, published_seasons
from agroclimate_core.periods import DekadPeriod, SeasonPeriod

SAMPLE = {
    "cdi": {"latest_year": 2026, "latest_month": 9, "latest_dekad": 11, "start_year": 2015, "2026": {"months": ["01"], "dekads": ["1", "11"]}},
    "longrange_forecast": {
        "latest_year": 2026,
        "latest_forecast_period_str": "SON",
        "2025": {"forecast_periods": [10, 11, 12], "forecast_periods_str": ["OND", "NDJ", "DJF"]},
        "2026": {"forecast_periods": [1, 9], "forecast_periods_str": ["JFM", "SON"]},
    },
}


class AvailabilityTests(unittest.TestCase):
    def test_dekad_range_uses_latest_markers_not_per_year_lists(self):
        earliest, latest = latest_dekad_range(SAMPLE, "cdi")
        self.assertEqual(earliest, DekadPeriod(2015, 1, 1))
        # per-year lists omit dekad 21 even though those files exist, so only 'latest_*' is trusted
        self.assertEqual(latest, DekadPeriod(2026, 9, 11))

    def test_unknown_product_names_the_alternatives(self):
        with self.assertRaises(KeyError) as caught:
            latest_dekad_range(SAMPLE, "nope")
        self.assertIn("cdi", str(caught.exception))

    def test_published_seasons_are_listed_per_start_year(self):
        seasons = published_seasons(SAMPLE, "longrange_forecast")
        self.assertIn(SeasonPeriod(2025, "NDJ"), seasons)
        self.assertIn(SeasonPeriod(2026, "SON"), seasons)
        self.assertEqual(len(seasons), 5)


CATALOG = {
    "datasets": [
        {"key": "combined_drought_hazard_era5", "available_periods": [{"year": 2026, "period": "SON"}, {"year": 2026, "period": "ASO"}]},
        {"key": "combined_drought_forecast_era5", "available_periods": []},
        {"key": "no_periods_field"},
    ]
}


class CatalogTests(unittest.TestCase):
    def test_lists_seasons_published_for_a_combined_product(self):
        self.assertEqual(
            combined_product_seasons(CATALOG, "combined_drought_hazard_era5"),
            [SeasonPeriod(2026, "ASO"), SeasonPeriod(2026, "SON")],
        )

    def test_product_without_periods_gives_empty_list(self):
        self.assertEqual(combined_product_seasons(CATALOG, "combined_drought_forecast_era5"), [])
        self.assertEqual(combined_product_seasons(CATALOG, "no_periods_field"), [])

    def test_unknown_product_names_the_alternatives(self):
        with self.assertRaises(KeyError) as caught:
            combined_product_seasons(CATALOG, "combined_drought_hazard_gpcc")
        self.assertIn("combined_drought_hazard_era5", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

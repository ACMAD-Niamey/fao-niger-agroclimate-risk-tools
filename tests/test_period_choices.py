from __future__ import annotations

import unittest

from agroclimate_core.period_choices import load_period_choices
from agroclimate_core.periods import DekadPeriod, SeasonPeriod
from agroclimate_core.workflow import WorkflowServices

AVAILABILITY = {"cdi": {"latest_year": 2026, "latest_month": 9, "latest_dekad": 11, "start_year": 2026}}
CATALOG = {
    "datasets": [
        {
            "key": "combined_drought_hazard_era5",
            "available_periods": [{"year": 2026, "period": "ASO"}, {"year": 2026, "period": "SON"}, {"year": 2025, "period": "OND"}],
        }
    ]
}


def services(availability=None, catalog=None, availability_error=None, catalog_error=None) -> WorkflowServices:
    def fetch_availability(_url):
        if availability_error:
            raise availability_error
        return availability or AVAILABILITY

    def fetch_catalog(_url):
        if catalog_error:
            raise catalog_error
        return catalog or CATALOG

    unused = lambda *a, **k: None  # noqa: E731
    return WorkflowServices(fetch_availability, fetch_catalog, unused, unused, unused)


class PeriodChoicesTests(unittest.TestCase):
    def test_dekads_run_newest_first_from_the_latest_published(self):
        choices = load_period_choices(services(), api_base_url="https://x", max_dekads=5)
        self.assertEqual(
            list(choices.dekads),
            [DekadPeriod(2026, 9, 11), DekadPeriod(2026, 9, 1), DekadPeriod(2026, 8, 21), DekadPeriod(2026, 8, 11), DekadPeriod(2026, 8, 1)],
        )
        self.assertEqual(choices.latest_dekad, DekadPeriod(2026, 9, 11))

    def test_the_list_stops_at_the_start_of_the_archive(self):
        availability = {"cdi": {"latest_year": 2026, "latest_month": 1, "latest_dekad": 11, "start_year": 2026}}
        choices = load_period_choices(services(availability=availability), api_base_url="https://x", max_dekads=36)
        self.assertEqual(list(choices.dekads), [DekadPeriod(2026, 1, 11), DekadPeriod(2026, 1, 1)])

    def test_seasons_are_newest_first_by_start_date(self):
        choices = load_period_choices(services(), api_base_url="https://x")
        self.assertEqual(list(choices.seasons), [SeasonPeriod(2026, "SON"), SeasonPeriod(2026, "ASO"), SeasonPeriod(2025, "OND")])
        self.assertEqual(choices.latest_season, SeasonPeriod(2026, "SON"))

    def test_an_unreachable_service_is_reported_not_raised(self):
        choices = load_period_choices(services(availability_error=ConnectionError("offline")), api_base_url="https://x")
        self.assertEqual(choices.dekads, ())
        self.assertIsNone(choices.latest_dekad)
        self.assertEqual(len(choices.seasons), 3)  # the other source still worked
        self.assertTrue(any("CDI" in problem for problem in choices.problems))

    def test_both_failing_gives_empty_choices_and_two_problems(self):
        choices = load_period_choices(
            services(availability_error=ConnectionError("x"), catalog_error=ConnectionError("y")), api_base_url="https://x"
        )
        self.assertEqual((choices.dekads, choices.seasons), ((), ()))
        self.assertEqual(len(choices.problems), 2)
        self.assertNotIn("ConnectionError: x", " ".join(choices.problems))  # plain wording, no raw exception text

    def test_a_missing_product_in_the_catalogue_is_a_problem_not_a_crash(self):
        choices = load_period_choices(services(catalog={"datasets": []}), api_base_url="https://x")
        self.assertEqual(choices.seasons, ())
        self.assertTrue(any("seasonal" in problem for problem in choices.problems))


if __name__ == "__main__":
    unittest.main()

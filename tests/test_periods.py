import unittest
from datetime import date

from agroclimate_core.periods import (
    DekadPeriod,
    PeriodUnavailableError,
    SeasonPeriod,
    resolve_dekad,
    resolve_season,
)


class DekadPeriodTests(unittest.TestCase):
    def test_from_date_and_previous_cross_month_and_year(self):
        self.assertEqual(DekadPeriod.from_date(date(2026, 5, 24)), DekadPeriod(2026, 5, 21))
        self.assertEqual(DekadPeriod.from_date(date(2026, 5, 10)), DekadPeriod(2026, 5, 1))
        self.assertEqual(DekadPeriod(2026, 5, 21).previous(), DekadPeriod(2026, 5, 11))
        self.assertEqual(DekadPeriod(2026, 5, 1).previous(), DekadPeriod(2026, 4, 21))
        self.assertEqual(DekadPeriod(2026, 1, 1).previous(), DekadPeriod(2025, 12, 21))

    def test_ordering_and_label(self):
        self.assertLess(DekadPeriod(2026, 9, 11), DekadPeriod(2026, 9, 21))
        self.assertEqual(DekadPeriod(2026, 9, 11).label, "2026-09-11")

    def test_invalid_dekad_is_rejected(self):
        with self.assertRaises(ValueError):
            DekadPeriod(2026, 10, 5)


class ResolveDekadTests(unittest.TestCase):
    LATEST = DekadPeriod(2026, 9, 11)
    EARLIEST = DekadPeriod(2015, 1, 1)

    def test_available_date_is_used_as_is(self):
        result = resolve_dekad(date(2026, 9, 5), self.LATEST, self.EARLIEST)
        self.assertEqual(result.period, DekadPeriod(2026, 9, 1))
        self.assertFalse(result.fallback)
        self.assertEqual(result.lag_dekads, 0)

    def test_unpublished_date_falls_back_to_latest_and_reports_lag(self):
        result = resolve_dekad(date(2026, 10, 12), self.LATEST, self.EARLIEST)
        self.assertEqual(result.period, DekadPeriod(2026, 9, 11))
        self.assertTrue(result.fallback)
        self.assertEqual(result.requested, DekadPeriod(2026, 10, 11))
        self.assertEqual(result.lag_dekads, 3)  # 10-11, 10-01, 09-21 are all missing

    def test_fallback_beyond_limit_fails(self):
        with self.assertRaises(PeriodUnavailableError) as caught:
            resolve_dekad(date(2026, 12, 1), self.LATEST, self.EARLIEST, max_fallback_dekads=3)
        self.assertIn("2026-09-11", str(caught.exception))

    def test_strict_mode_never_falls_back(self):
        with self.assertRaises(PeriodUnavailableError):
            resolve_dekad(date(2026, 10, 12), self.LATEST, self.EARLIEST, strict=True)

    def test_before_archive_start_fails(self):
        with self.assertRaises(PeriodUnavailableError):
            resolve_dekad(date(2010, 6, 1), self.LATEST, self.EARLIEST)


class SeasonTests(unittest.TestCase):
    PUBLISHED = [SeasonPeriod(2025, "OND"), SeasonPeriod(2025, "NDJ"), SeasonPeriod(2025, "DJF")] + [
        SeasonPeriod(2026, label) for label in ("JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON")
    ]

    def test_window_wraps_the_year(self):
        djf = SeasonPeriod(2025, "DJF")
        self.assertTrue(djf.contains(date(2025, 12, 20)))
        self.assertTrue(djf.contains(date(2026, 2, 28)))
        self.assertFalse(djf.contains(date(2026, 3, 1)))

    def test_invalid_label_is_rejected(self):
        with self.assertRaises(ValueError):
            SeasonPeriod(2026, "XXX")

    def test_prefers_latest_starting_season_containing_the_date(self):
        result = resolve_season(date(2026, 10, 12), self.PUBLISHED)
        # ASO and SON both contain 12 Oct; SON started later and is also the newest published.
        self.assertEqual(result.period, SeasonPeriod(2026, "SON"))
        self.assertFalse(result.fallback)

    def test_date_after_all_published_uses_latest_and_flags_fallback(self):
        result = resolve_season(date(2027, 2, 1), self.PUBLISHED)
        self.assertEqual(result.period, SeasonPeriod(2026, "SON"))
        self.assertTrue(result.fallback)

    def test_strict_and_empty(self):
        with self.assertRaises(PeriodUnavailableError):
            resolve_season(date(2027, 2, 1), self.PUBLISHED, strict=True)
        with self.assertRaises(PeriodUnavailableError):
            resolve_season(date(2026, 1, 1), [])


if __name__ == "__main__":
    unittest.main()

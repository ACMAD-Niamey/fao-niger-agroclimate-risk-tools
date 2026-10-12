import unittest

from fao_niger_agroclimate.risk import (
    RiskInputs,
    calculate_exposure_score,
    calculate_hazard_score,
    calculate_record,
    calculate_risk_score,
    classify_risk,
    score_cdi,
)


class RiskScoringTests(unittest.TestCase):
    def test_score_cdi_labels_and_numeric_values(self):
        self.assertEqual(score_cdi("No drought"), 0)
        self.assertEqual(score_cdi("Watch"), 1)
        self.assertEqual(score_cdi("warning"), 2)
        self.assertEqual(score_cdi("Alert"), 3)
        self.assertEqual(score_cdi("2"), 2)

    def test_hazard_uses_cdi_only_when_supporting_indicators_are_missing(self):
        self.assertEqual(calculate_hazard_score("warning"), 2)

    def test_hazard_renormalizes_available_supporting_indicators(self):
        score = calculate_hazard_score("warning", fapar_anomaly="severe", soil_moisture_anomaly="moderate")
        self.assertAlmostEqual(score, 2.2)

    def test_exposure_score_uses_documented_weights(self):
        score = calculate_exposure_score(3, 2, 1)
        self.assertAlmostEqual(score, 2.25)

    def test_risk_score_without_vulnerability_uses_fallback_formula(self):
        self.assertAlmostEqual(calculate_risk_score(2.2, 2.35), 2.26)

    def test_risk_score_with_vulnerability_uses_full_formula(self):
        self.assertAlmostEqual(calculate_risk_score(2.2, 2.35, 3), 2.405)

    def test_risk_class_thresholds(self):
        self.assertEqual(classify_risk(0.9), "low")
        self.assertEqual(classify_risk(1.0), "moderate")
        self.assertEqual(classify_risk(1.7), "high")
        self.assertEqual(classify_risk(2.4), "very high")

    def test_calculate_record_returns_all_outputs(self):
        result = calculate_record(
            RiskInputs(
                cdi="alert",
                fapar_anomaly="severe",
                soil_moisture_anomaly="moderate",
                cultivated_exposure=3,
                rangeland_exposure=2,
                water_point_exposure=1,
            )
        )
        self.assertEqual(
            result,
            {
                "hazard_score": 2.8,
                "exposure_score": 2.25,
                "risk_score": 2.58,
                "risk_class": "very high",
            },
        )

    def test_rejects_scores_outside_zero_to_three(self):
        with self.assertRaises(ValueError):
            calculate_risk_score(4, 1)


if __name__ == "__main__":
    unittest.main()

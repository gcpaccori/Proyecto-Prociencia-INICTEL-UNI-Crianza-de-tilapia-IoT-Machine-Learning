import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from backend.app.models_engine.ml.tilapia_interval_growth import (
    EnvironmentalSegment, GrowthCovariates, GrowthTrainingInterval,
    IntervalGrowthPilot, grouped_benchmark, interval_exposure,
)


class ExposureTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.issue = self.start + timedelta(days=1)

    def segment(self, start=0, end=24, oxygen=4):
        return EnvironmentalSegment(self.start+timedelta(hours=start),
            self.start+timedelta(hours=end), 28, oxygen, "observed", self.issue)

    def test_subdaily_hypoxia_differs_from_daily_mean(self):
        # Both have daily OD = 4. Hypoxia exposure differs: 24 vs 0 mg*h/L.
        a = interval_exposure(self.start,self.issue,self.issue,
            [self.segment(0,12,1),self.segment(12,24,7)])
        b = interval_exposure(self.start,self.issue,self.issue,[self.segment()])
        self.assertEqual(a['do_mean_mg_l'], b['do_mean_mg_l'])
        self.assertEqual(a['oxygen_deficit_mg_h_l'],24)
        self.assertEqual(b['oxygen_deficit_mg_h_l'],0)

    def test_future_observed_water_is_not_forecast(self):
        with self.assertRaisesRegex(ValueError,'future observations'):
            interval_exposure(self.start,self.issue,self.start,[replace(self.segment(),available_at=self.start)])

    def test_model_trained_after_issue_cannot_supply_forecast(self):
        s=replace(self.segment(),kind='forecast',available_at=self.start,
            trained_until=self.issue,model_version='rf-v1')
        with self.assertRaisesRegex(ValueError,'trained after'):
            interval_exposure(self.start,self.issue,self.start,[s])

    def test_valid_frozen_forecast_covers_future(self):
        s=replace(self.segment(),kind='forecast',available_at=self.start,
            trained_until=self.start-timedelta(days=1),model_version='rf-v1')
        f=interval_exposure(self.start,self.issue,self.start,[s])
        self.assertEqual(f['forecast_fraction'],1)

    def test_missing_day_is_not_silently_interpolated(self):
        with self.assertRaisesRegex(ValueError,'insufficient'):
            interval_exposure(self.start,self.issue,self.issue,[self.segment(0,12)])

    def test_overlapping_segments_rejected(self):
        with self.assertRaisesRegex(ValueError,'overlapping'):
            interval_exposure(self.start,self.issue,self.issue,[self.segment(),self.segment(12,24)])

    def test_nan_and_naive_time_rejected(self):
        with self.assertRaisesRegex(ValueError,'finite'):
            interval_exposure(self.start,self.issue,self.issue,[replace(self.segment(),do_mg_l=float('nan'))])
        with self.assertRaisesRegex(ValueError,'timezone'):
            interval_exposure(self.start.replace(tzinfo=None),self.issue,self.issue,[self.segment()])


class PilotTests(unittest.TestCase):
    def rows(self):
        return [GrowthTrainingInterval(study_id='s1',cohort_id=f'tank{i}',duration_days=60,
            initial_weight_g=8+i/10,final_weight_g=50+i,temperature_mean_c=30,
            do_mean_mg_l=4,source_reference='doi:example') for i in range(12)]

    def test_target_does_not_enter_prediction_covariates(self):
        model=IntervalGrowthPilot().fit(self.rows())
        row=self.rows()[2]
        self.assertEqual(model.predict(row)['weight_g'],
                         model.predict(replace(row,final_weight_g=9999))['weight_g'])
        cov=GrowthCovariates(study_id='s2',cohort_id='x',duration_days=60,
            initial_weight_g=8.2,temperature_mean_c=30,do_mean_mg_l=4,source_reference='forecast')
        self.assertAlmostEqual(model.predict(cov)['weight_g'],model.predict(row)['weight_g'])

    def test_out_of_domain_refuses_numeric_prediction_by_default(self):
        model=IntervalGrowthPilot().fit(self.rows())
        prediction=model.predict(replace(self.rows()[0],initial_weight_g=1,duration_days=1))
        self.assertIsNone(prediction['weight_g'])
        self.assertFalse(prediction['production_ready'])
        self.assertIsNone(prediction['confidence'])

    def test_missing_group_and_three_dates_do_not_enable_training(self):
        with self.assertRaises(ValueError):
            IntervalGrowthPilot().fit(self.rows()[:3])
        with self.assertRaises(ValueError):
            grouped_benchmark(self.rows(), ['same']*12,environmental=True)

    def test_grouped_holdout_and_weight_loss_supported(self):
        rows=self.rows(); rows[0]=replace(rows[0],final_weight_g=7)
        result=grouped_benchmark(rows,['a']*6+['b']*6,environmental=False)
        self.assertEqual(result['n_intervals'],12)
        self.assertEqual(result['n_groups'],2)
        self.assertEqual(result['n_studies'],1)


if __name__=='__main__':
    unittest.main()

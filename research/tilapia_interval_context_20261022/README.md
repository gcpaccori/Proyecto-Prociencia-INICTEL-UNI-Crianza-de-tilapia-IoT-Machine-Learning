# Single interval GP: measured water, entered feed and observed growth

This experiment implements the proposed interval dataset and four matched ML
ablations. The response is an observed **final mean weight**, conditional on the
last measured weight, elapsed interval and available context. No fish growth
formula, sensor forecast stack or Gaussian curve pseudo-labels are used.

The existing production growth predictor is not replaced. An authenticated private
API exposes the candidate and its failed development comparison; the existing
Laravel growth panel shows that comparison separately from its active forecasts.

## Reproduce

Use the pinned training requirements in `../tilapia_gaussian_20261022/requirements-training.txt`.
Obtain a fresh, read-only, consistent MySQL snapshot with that directory's
`export_mysql.py` inside the trusted backend (credentials remain on the server).
From the repository root:

```sh
PYTHONPATH=. python research/tilapia_interval_context_20261022/train_interval.py \
  --snapshot /private/path/snapshot.json.gz --out /private/path/evidence
```

The protocol is written before fitting. Four fixed variants share the same
eligible intervals: initial weight/time; plus water; plus entered feed; plus both.
Each is one GP with a linear kernel, Matérn 3/2 kernel and white noise. Only three
amplitudes are optimized by training-prefix marginal likelihood. Physical scales
are fixed, not selected from evaluation outcomes. Mean-weight sampling SE enters
the likelihood. Conditional uncertainty does not propagate initial-weight sampling
error, interval dependence or fitted hyperparameter uncertainty.

The six observed intervals yield five water-eligible intervals. The last interval
has only about 30% observed oxygen hours and is excluded from **all** primary fits
and comparisons. Expanding-prefix evaluation starts after two training intervals
and evaluates three dates already known during project development. It is a
retrospective nowcast, not a forecast issued before the interval's environment or
feed was observed.

## Observed outcome, not a success claim

On 7 August, 13 September and 26 September 2026:

| Inputs | MAE (g) |
| --- | ---: |
| Initial weight/time | 30.811 |
| Initial weight/time + water | 26.346 |
| Initial weight/time + entered feed | 31.583 |
| Initial weight/time + entered feed + water | 31.291 |
| Last observed weight reference | 15.234 |

The full candidate failed to improve the reference. Three correlated, previously
examined dates cannot establish a general effect of feed or water. No further
search against these dates was used to manufacture a better score.

## Provenance and safeguards

* The target endpoint's entered feed total is **unverified**, as are historic
  physical clock alignment and receipt availability. Diagnostic use is explicit.
* FCR, final biomass, computed growth rates, and target-dependent feed schedules
  cannot be submitted through the API. The builder never reads those inputs.
* Missing water is not interpolated. Water must reach 70% interval coverage for
  every variable and its final gap must not exceed 48 h.
* Light, feed protein and population movement events lack sufficient audited
  paired records and are not silently fabricated or imputed.
* Published Yu et al. 2021 means remain **reference only**: no aligned continuous
  interval environment or verified delivered-feed quantities were downloaded.
* Current operational predictions return 503 until a new audited and biologically
  validated artifact exists. Extra request fields are rejected. Private service
  bearer authentication and existing Laravel module permissions are preserved.
* JSON inference independently matches scikit-learn; no pickle is required to
  serve the trained model.

Private routes: `GET /api/v1/models/tilapia-growth-interval-context/status` and
`POST /api/v1/models/tilapia-growth-interval-context/predict`. The latter defaults
to blocked operational mode; `retrospective_fit_diagnostic` is explicitly an
in-sample/development diagnostic, never biological validation.

The pre-existing hourly Gaussian CSV is a retrospective posterior reconstruction.
The user's selected rows 3235:3248 cover 4–5 October and retain
`estimated_not_measured=True`; none is a new training label.

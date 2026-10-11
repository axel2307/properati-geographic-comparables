# Properati geographic comparables

A small Streamlit portfolio project that explains **filtered comparables followed by geographic neighbours**. The default uses a minimized projection of the dataset supplied by the author, who declared it fictional and authorized publication of the projection. This declaration has not been independently verified. The full source file is not included.

The interface is in Rioplatense Spanish. It labels the data as an author-provided demonstration and makes no claim to represent market prices, completed sales or a professional valuation. The project and source filename do not establish an upstream provider or licence.

## Run locally

Use Python 3.12, which is the version verified with the pinned dependencies. From this repository:

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Install test dependencies with `python -m pip install -r requirements-dev.txt`, then run checks with `python -m pytest -q`. Dependency pins and GitHub Actions are provided in this repository. The Streamlit Community Cloud entry point is `app.py`; see `DEPLOYMENT.md` for deployment instructions.

Uploads are disabled by default, including on a public server. To opt in on your own computer before starting Streamlit, set `PROPERATI_ALLOW_UPLOADS=1`:

```powershell
# Windows PowerShell
$env:PROPERATI_ALLOW_UPLOADS = "1"
python -m streamlit run app.py
```

```sh
# macOS/Linux
PROPERATI_ALLOW_UPLOADS=1 python -m streamlit run app.py
```

Keep this variable unset on a public demonstration. Enabling it requires a separate in-app acknowledgement before the file picker becomes available.

## What changed from the legacy approach

- Haversine distance in kilometres replaces Euclidean distance between latitude and longitude.
- Property type, rooms, total area and covered-area ratio all participate in filtering. Every tolerance, radius and maximum neighbour count is visible.
- There are no bathroom or amenity controls: the available schema cannot reliably support them. A missing field never silently means “no”.
- Three to five comparables are required. With fewer than three, the app returns insufficient evidence. It never silently relaxes a filter.
- Positive areas, covered area no greater than total, finite coordinates, rooms and filter bounds are validated before division or selection.
- Duplicate handling and spatial holdout happen before evaluation. The user-facing prediction also uses training rows only.

## Method

For a submitted property, first keep rows with the exact same property type. Keep rooms within the selected integer tolerance, total area within the selected percentage of the query area, and covered/total area ratio within the selected **percentage-point** tolerance. For example, 80% coverage with a 10-point tolerance admits ratios from 70% to 90%.

Compute great-circle distances using the Haversine formula with Earth radius 6,371.0088 km. Keep rows inside the visible radius and select the nearest `k` (default 5, allowed 3-5). Equal-distance ties use stable input order. If fewer than 3 remain, do not predict. Otherwise use their unweighted mean USD per square metre; multiply it by the query's total area for the demonstration reference. Coordinates in the bundled projection are rounded to three decimal places, which can affect neighbours, spatial groups and results; distances do not recover the original precision.

The displayed minimum and maximum are the **observed range among selected comparables**. They are not a confidence interval, prediction interval, or calibrated measure of uncertainty. The small sample and unweighted mean can be sensitive to outliers. Scaled means and safe medians avoid summation overflow. A nonfinite or nonpositive resulting total is rejected explicitly, without displaying an invalid price.

## Data contract and privacy

`load_demo()` reads and validates `data/demo.csv`, the authorized eight-column projection of the author's file: `property_type`, `neighborhood`, `area_total`, `area_covered`, `rooms`, `lat`, `lon` and `price_usd`. It contains no free-text descriptions, addresses, contacts or source identifiers; latitude and longitude are rounded to three decimal places. The app uses this file, not a replacement generator. `synthetic_data()` remains available only as a generated test fixture.

The shared `data.py` pipeline returns a validated, whitelisted frame with those eight columns plus derived `usd_m2`, `ratio` and `spatial_group`. It requires finite numeric values, positive USD prices and areas, positive covered area no greater than total, integer rooms in 1-20, recognized locality labels and plausible CABA coordinates. The geographic bounding box is not an official city-boundary polygon. USD/m² and covered ratio are derived from the validated price and areas rather than trusting supplied ratio fields.

The separate, optional `load_csv` upload path accepts CSV or tab-separated files in the original eleven-column schema: `operation`, `property_type`, `place_name`, `state_name`, `lat`, `lon`, `price`, `currency`, `surface_total_in_m2`, `surface_covered_in_m2` and `rooms`. It filters the operation, currency and CABA locality before returning the canonical frame. See `data.py` for accepted labels and bounds. Other uploads do not inherit the author's fictional-data declaration; the uploader is responsible for their provenance, dates, truthfulness and permission to process them. Their results likewise do not establish market prices.

Deduplication uses location and property features independently of the price before partitioning. This reduces repeated-observation leakage but can also collapse distinct units with identical recorded features. It cannot guarantee identification of every repetition; rounded or shifted coordinates and changing features remain limitations. Filtering to complete, supported observations also introduces selection bias.

Publication of the minimized projection is based on the author's explicit authorization and declaration that the supplied dataset is fictional. This is not an independently verified upstream licence and does not establish provenance from a service with a similar name. Only the approved minimized projection belongs in this repository; the complete file, private source paths and local audit artifacts are excluded.

Uploads require an explicit acknowledgement of permission and processing location. The app does not persist uploads, use a data cache, or display individual rows, addresses, descriptions or exact source coordinates. It shows aggregate counts, distance ranges and metrics. The bundled `data/demo.csv` is a public repository artifact, so its minimized rows are accessible separately from the interface. A deployed Streamlit server receives uploads: "processed locally" means local to the running server, not automatically the visitor's computer. Run on your own computer for private files. Hosting providers may have their own logging and retention policies. The application upload limit is 200 MiB, matching the loader. Query widgets cap area at 10,000 m² for usability; the evaluation accepts all validated positive areas and reports coverage normally.

## Evaluation

`split_data` creates reproducible, disjoint spatial groups after deduplication (seed 42). This evaluates the demonstration dataset. It is not a forecast or a market-accuracy study. Adjacent cells can still contain nearby observations, so this split reduces location overlap without guaranteeing full spatial independence. No reliable observation timestamp is used, and download dates are not treated as observation dates.

For responsiveness, evaluation samples at most 300 held-out rows uniformly without replacement using seed 42. All model fitting and the baseline median use training rows only. The baseline predicts the training median **USD/m²**. Model and baseline MAE and median absolute error are computed on the **same held-out cases for which at least three comparables and a finite positive reference exist**. Coverage is covered rows divided by sampled rows; the app reports both the sample and full holdout sizes. Empty coverage produces no error metrics.

Changing filters changes the covered subset. Errors from different queries or filter settings therefore cannot be compared as if the population were unchanged. The holdout is interactive, so repeated tuning against it may overfit the evaluation; reserve a fresh final test set for any formal model comparison. Metrics describe performance on the author-provided demonstration data only and do not validate accuracy on real properties. This README makes no fixed accuracy claim.

## Limitations

The author's fictional-data declaration is not independently verified, and demonstration records may be inconsistent or unrepresentative. The method does not model condition, building age, floor, orientation, expenses, views, record quality, negotiating conditions or changes in the market. Geographic proximity does not guarantee comparable quality, and Haversine distance is not travel distance. Broad tolerances improve coverage while allowing less similar observations. Sparse groups may return no estimate. Nothing in the application is a professional appraisal.

## Repository structure

- `app.py`: Streamlit interface, aggregate reporting and upload privacy notice.
- `model.py`: query/filter validation, Haversine neighbours and holdout evaluation.
- `data.py`: demo loading, input validation, deduplication, spatial split and a generated test fixture.
- `data/demo.csv`: authorized minimized projection of the author-provided dataset.
- `tests/`: checks for data integrity, distance units, meaningful filters, scarce evidence and evaluation isolation.

See `PRIVACY.md` and `DEPLOYMENT.md` for processing and deployment details.

# ATLAS 2.0 — Urban Mobility Command Center

**Historical pickup demand intelligence for regional fleet planning.** ATLAS is the team and dashboard name shown in the app title. The two-page Streamlit dashboard serves a regional taxi operations manager: the Command Center shows recorded pickups by time and location, while Demand Analysis examines daily and weekday patterns. It does not measure unserved demand or real-time supply.

## STEP 1 — Dataset & Decision Maker

- **Dataset:** [Kaggle NYC Taxi Trip Duration](https://www.kaggle.com/competitions/nyc-taxi-trip-duration/data), a sampled and cleaned competition extract based on 2016 NYC Yellow Cab records originally published by the NYC Taxi and Limousine Commission.
- **Observed training data:** `train.csv` has **1,458,644 rows and 11 columns**, with pickup timestamps **2016-01-01 00:00:17 to 2016-06-30 23:59:39**. Each row represents one recorded trip whose meter was engaged. These are real historical trips in a competition sample, not all attempted rides.
- **Raw vs processed:** The inspected `train.csv` was **200,589,097 bytes (200.59 MB)**. Only that file was analyzed. The reproducible pipeline kept **1,458,397** pickups in a broad NYC box and grouped them by date, hour, day type, and 0.01° pickup grid. The deployed `data/processed/demand_aggregated.csv` has **239,648 rows and 9,310,779 bytes (9.31 MB)**; its counts sum to all retained pickups. `data_profile.json` records validation and period. All three raw Kaggle CSV files have now been removed locally; they are not required to run the app.
- **Decision maker:** A **Regional Operations Manager** assessing where and when recorded pickup volume concentrates before scheduling or repositioning vehicles.

## STEP 2 — Business Justification

1. **Who uses it and how often?** A regional operations manager reviews the historical view at the weekly staffing meeting and before each planned peak shift. In a future live system, they would also check each 15-minute refresh during a peak. This Kaggle snapshot never refreshes itself.
2. **What decision does it support?** Which hour and grid cells warrant a closer look for extra capacity. **If the regional operations manager sees** a sustained pickup concentration in adjacent grids during an upcoming shift, **they will** compare it with available vehicles and consider repositioning or changing the next schedule. This is a prompt for an operational check, not an automatic dispatch order.
3. **What would the manager do without it?** Manually compare large trip extracts or separate hourly summaries before changing a schedule. That repeated work delays recognizing a sustained hotspot and risks leaving vehicles idle in quiet grids while coverage is thin in busy grids. The source has no driver-supply or wait-time data, so we cannot put a defensible dollar amount on that cost.
4. **Why a dashboard instead of a weekly email, report, or single alert?** The manager repeatedly needs to change the date, day type, and hour, then compare nearby grids and the length of a peak. A fixed email or report cannot answer those follow-up questions without a new extract. An alert can flag an exceptional interval but cannot show the surrounding map and hourly pattern needed to decide whether a staffing or positioning check is warranted.

Recorded trips are **not complete market demand**. The source has no online-driver inventory, unmet requests, wait times, or real-time congestion measures.

## STEP 3 — Dashboard Design

The Command Center puts **three headline metrics in one `st.columns` row** at the top of the decision panel, so the selected hour can be assessed quickly. The spatial map sits beside the panel and takes most of the width because the next question is **where** pickups concentrate. The hourly chart explains whether the selected hour is an isolated spike or part of a sustained peak; the map-specific timeline sits beneath the map. Longer-range charts are on a separate page so they do not crowd the primary decision view.

```text
Header: ATLAS team name + manager/decision caption
Decision panel: three metrics → hourly context → date/day-type filters  |  Map: pickup locations → hour timeline
Footer: source period + proposed production refresh
```

This order answers **how much is happening now**, then **where and for how long**, before asking the manager to change the cohort or inspect deeper analysis.

- **Pickups**, **Active Grids**, and **Top Grid** are the three side-by-side `st.metric` values. They show the selected-hour pickup count, the number of 0.01° cells with recorded pickups, and the busiest cell's pickup count. The top-grid caption gives its coordinates without inventing a neighborhood name; the heading shows the selected hour, while a small caption gives the selected-period total and peak hour. All values follow the map's hour and have no fabricated growth deltas. These are recorded pickup grids, not available-vehicle counts.
- **Spatiotemporal Demand Map** is dominant because the decision is geographic. PyDeck columns encode grid counts in color and square-root-scaled height. The color baseline is the maximum hourly grid count across all 24 hours for the current date/day-type filter, so playback does not rescale each frame. Tooltip counts remain untransformed. The selected hour, active zones, and selected-hour pickups appear above it.
- **Hourly Pickup Demand** is the only supporting chart. Its compact bars sit beside the map, distinguish an isolated spike from a longer high-volume period, and highlight both the selected and peak hours. The selected-hour highlight advances with the map.
- **Filters** are limited to a draggable Date Range slider and Day Type (All, Weekday, Weekend). The selected cohort carries between the two pages. The hour slider and Play/Pause inspect the map rather than change the business cohort. The Command Center starts playing on first entry and keeps playing while filters or the hour slider change; the playback button pauses or resumes it.

We deliberately **do not show Passenger Count Distribution** because it does not directly guide regional vehicle placement here. We also **do not show Trip Duration Distribution**: useful for another question, but less relevant than pickup hotspots to this decision.

**Limits:** The competition file is a sample; pickups omit unserved requests. There are no supply-side measures. A 0.01° grid is approximate, not an administrative neighborhood. The broad NYC box can include nearby areas and exclude distant airport pickups. This static 2016 snapshot cannot support live dispatch decisions.

### ATLAS 2.0 Dashboard Design

The map takes roughly seventy percent of the Command Center's desktop width because the operations question starts with **where** pickups concentrate. The narrower left panel starts with a prominent Demand Analysis page card, then contains the compact three-column metric row, the 24-hour profile, and filters. The timeline sits below the map and changes the hour shown in the map and left-side metrics; the date and day-type cohort remains fixed until a filter changes. Longer-range charts belong on the separate Demand Analysis page, where the title sits beside the Command Center return link. Both pages use the supplied Statue of Liberty night image behind a dark overlay; the Command Center's left panel is translucent so more of the image remains visible. The image is served from `static/nyc-night.png` using a relative URL so it works locally and under Streamlit Community Cloud's app path.

All 24 map frames share one color and height denominator for the selected date range and day type. Square-root visual scaling makes less busy grids visible while hover displays their true recorded counts. The legend runs from low blue through cyan and amber to high orange; a saturated column means the selected grid is near the current filter's upper bound. **Do not compare colors across different filter selections** without considering that their fixed bounds are recalculated. The left-side hourly readouts, highlighted chart bar, map, and selected-hour strip all use the hour on the timeline.

Playback starts automatically at 00:00 using a timed Streamlit fragment, advances every 2.5 seconds, and loops after 23:00. The slower interval gives the browser time to draw each 3D map frame on Community Cloud. Each tick replaces the left metrics and right map together, while the 24 histogram bars, filters, page link, and masthead remain mounted. A small style update moves the selected-hour highlight across the fixed bars, avoiding Plotly chart remounts during playback. Cached filtered aggregates avoid recomputing the cohort each frame. The app reads the CSV once per file change and sends only one hour of grids to PyDeck per frame. The first button press pauses it. It does not show live vehicle positions, available drivers, unmet requests, or real-time demand. PyDeck's Streamlit chart API does not expose the user's live pan/zoom camera to Python, so a chart redraw during playback may restore its configured NYC view. The fixed chart key minimizes unnecessary remounts, but exact camera preservation is not guaranteed.

### Demand Analysis page

The link at the top of the Command Center's left panel opens a second page for longer-range planning. Its compact header places the title and planning summary beside the Command Center return link, directly above the date slider. Its **daily pickup line** shows recorded trips by observed date with the selected-period median as a reference, helping managers identify dates that merit a staffing or event-calendar review. Its **weekday bar chart** shows *average pickups per observed day of that weekday*, rather than raw weekday totals, so a weekday appearing more often in the date selection does not look artificially busier. Hover shows the mean, the number of observed dates, and their total pickups. Three compact metrics summarize average volume per observed day, the highest-volume date, and the weekday with the highest mean. Both charts use the same date/day-type cohort as the Command Center and the same pre-aggregated CSV. A missing date is not silently treated as zero demand.

### EDA and cleaning evidence

The full scan found **no missing values** in the 11 columns and **no invalid pickup datetimes or world coordinates**. The NYC box (latitude **40.45–40.95**, longitude **−74.30 to −73.65**) excludes **247** pickups and retains **1,458,397**. There are **zero** nonpositive trip durations and **four** longer than 24 hours. Duration extremes are reported but kept because duration is not used in the pickup count. Among retained pickups, **1,042,227** are on weekdays and **416,170** on weekends; these totals cover unequal numbers of days and are not average daily rates. The busiest observed hour is **18:00–19:00**, with **90,585** pickups across the study period. The executed [EDA notebook](notebooks/eda.ipynb) shows source shape, field types and missingness from the saved full-source profile, plus Pandas and Matplotlib distributions and spatial/time relationships from the processed aggregate. The original raw CSV is no longer needed to view or rerun those aggregate plots.

To rebuild the aggregate, first download `train.csv` from Kaggle and place it in `data/`, then run:

```bash
uv run python -m src.data_processing
```

The pipeline reads in chunks, parses pickup time, validates coordinates, keeps pickups in the documented box, and groups by date/hour/day type/grid. It chooses 0.01° because this daily aggregate is under 25 MB. If a future source is too large, it retries wider grids instead of truncating rows. The app **never** processes the million-row raw CSV on startup.

## STEP 4 — Refresh Strategy

- **Production data refresh frequency:** **Every 15 minutes is proposed for a future system** connected to a continuing order stream. It is not this Kaggle snapshot's refresh frequency.
- **Dashboard review frequency:** At the weekly staffing meeting and before each planned peak shift; in a future live system, at each 15-minute refresh during a peak. This is distinct from the data refresh schedule.
- **Metric and action threshold:** Track recorded pickups in each operating corridor against the historical baseline for the same day type and time of day. A **pilot rule** is at least **20% and 20 pickups above that baseline for two consecutive 15-minute windows**. If triggered, check available vehicles before deciding whether to reposition; do not dispatch from pickup counts alone. The thresholds are proposals to calibrate with live 15-minute demand and supply data, not findings validated by this hourly 2016 snapshot.
- **Cost of stale data:** Delayed hotspot recognition can lead to late repositioning or unnecessary idle coverage. This dataset cannot quantify that cost.

Fifteen minutes is a practical proposed refresh cadence, rather than reacting to every trip. The manager checks at that cadence only during peaks. A real system would also need live ingestion, driver availability, reliability checks, and operational validation.

## STEP 5 — Run & Deploy

Use **Python 3.14**. The project has a standalone `pyproject.toml`, `uv.lock`, and matching runtime `requirements.txt`. From the repository root (the local source folder is `taxi-trip`):

```bash
uv sync
uv run streamlit run app.py
```

The processed CSV and profile are included for runtime; `.gitignore` excludes the large raw Kaggle files, which are absent from this local project. To reproduce processing, download `train.csv` into `data/`, then run the rebuild command. The source is subject to [Kaggle competition rules](https://www.kaggle.com/competitions/nyc-taxi-trip-duration/rules); review them before redistributing data or making a public deployment.

For [Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), use `app.py` as the entrypoint and select Python 3.14 in Advanced settings. The deployed repository already places `app.py`, `.streamlit/config.toml`, `assets/style.css`, `uv.lock`, and `requirements.txt` at its root. The [CARTO Dark Matter basemap](https://docs.carto.com/carto-for-developers/carto-for-react/guides/basemaps) requires browser internet access, but no private token.

### Project structure

```text
ATLAS-NYC-Urban-Mobility-Intelligence/
├── app.py
├── src/
│   ├── data_loader.py
│   ├── data_processing.py
│   ├── metrics.py
│   └── visualizations.py
├── data/
│   └── processed/
│       ├── demand_aggregated.csv # 9.31 MB runtime dataset
│       └── data_profile.json
├── notebooks/eda.ipynb
├── assets/style.css
├── static/nyc-night.png
├── 自由女神与夜景.png
├── .streamlit/config.toml
├── pyproject.toml
├── uv.lock
└── requirements.txt
```

# Headcounts: Developer Reference

A Flask web app for browsing course enrollment data at [Minnesota State University Moorhead](http://www.mnstate.edu). Data is scraped from the public MinnState course search tool and served as a searchable, filterable table with download support and an analytics dashboard.

**Stack:** Python 3.12, Flask, Polars, DataTables.js, Chart.js, gunicorn, deployed on Dokku

---

## Project layout

```
headcounts-web/
├── app.py                   # Flask application and all routes
├── utils.py                 # Data processing, formatting, and analytics helpers
├── models.py                # WTForms form definition and dropdown choices
├── config.py                # App-wide constants (paths, URLs, default term)
├── config_terms.py          # SEMESTERS_LIST — all term codes and display names
│
├── scrape.py                # Scraper: fetches course data from MinnState and writes CSV
├── update_data_table.py     # Data updater: merges new scraped data into the main dataset
│
├── all_enrollments.parquet  # Primary data file read by the app at runtime
├── all_enrollments.csv      # CSV mirror of the parquet file (for export reference)
│
├── templates/
│   ├── base.html            # Shared layout: header, nav, footer, disclaimer
│   ├── search.html          # Search form page (the home page)
│   ├── results.html         # Filtered results table with DataTables
│   └── analytics.html       # Analytics dashboard with Chart.js charts
│
├── static/
│   ├── script.js            # Client-side form logic and notice dismiss handler
│   └── css/
│       ├── app.css          # Master CSS import — loads all layers in order
│       ├── utilities.css    # Single-purpose utility classes (margins, flex, etc.)
│       ├── foundation/
│       │   ├── tokens.css   # CSS custom properties (colors, spacing, type scale)
│       │   └── base.css     # Element-level resets and defaults
│       ├── layout/
│       │   └── shell.css    # App shell: header, nav, main, footer, disclaimer
│       ├── components/
│       │   ├── cards.css    # .card, .card-muted, .table-card, .chart-card, .stat-card
│       │   ├── buttons.css  # .button variants
│       │   ├── forms.css    # Form fields, labels, validation states
│       │   ├── tables.css   # Table base styles, sticky header
│       │   └── alerts.css   # .notice component (flash messages)
│       └── pages/
│           ├── search.css   # .hero-card, search page layout
│           ├── results.css  # .results-layout, .results-info, .results-actions, .empty-state
│           └── analytics.css # Analytics page layout, stat grid, chart containers
│
├── daily_update_script.sh   # Cron-driven scrape + update + commit + deploy (see below)
├── .env.example             # Template for the required .env file
├── Procfile                 # Process definition for gunicorn, used by Dokku
├── requirements.txt         # Production Python dependencies
└── requirements-dev.txt     # Dev-only tools (black, flake8, ruff, pytest)
```

---

## Key files in detail

### `app.py`

All Flask routes live here. The main ones:

| Route | Method | Function | Description |
|---|---|---|---|
| `/` | GET/POST | `index` | Renders the search form; on POST validates and redirects to the filtered URL |
| `/<subject>/...` | GET | `filtered_view` | Filters parquet data, calculates stats, renders results page |
| `/data/<subject>/...` | GET/POST | `data_view` | DataTables server-side endpoint: handles `draw`, `start`, `length`, search, and sort |
| `/csv/<subject>/...` | GET | `csv_view` | Returns filtered data as a CSV download; accepts `?q=` for text search |
| `/api/<subject>/...` | GET | `api_view` | Returns raw filtered data as Polars JSON |
| `/analytics` | GET | `analytics` | Renders the Chart.js dashboard; accepts `?term=` query param |
| `/download/<filename>` | GET | `download` | Serves cached CSV/Excel files from `viewed-csvs/` |

### `utils.py`

Data processing and helper functions:

- `filter_data(tbl, subject, spec1, spec2)` — applies URL-based filters to the Polars LazyFrame. Handles colleges, LASC/WI, course numbers, wildcards, and term codes.
- `_build_display_table(render_me)` — formats a collected DataFrame for display: renames columns, formats money and dates, converts course IDs to HTML links. Returns `(columns, rows)` as plain lists.
- `process_data_request(render_me, path, subj_text)` — calculates stats (SCH, seats, tuition), generates download files, extracts display column names, and renders `results.html`. Table rows are loaded client-side via the `/data/` Ajax endpoint.
- `get_analytics_data(table, current_term)` — aggregates enrollment data for the analytics dashboard.
- `calc_sch`, `calc_seats`, `calc_tuition` — individual stat helpers.
- `generate_datafiles` — writes CSV and Excel download files to `viewed-csvs/`.
- `build_url(form)` — converts the search form submission into a filtered URL path.

### `config.py` and `config_terms.py`

`config.py` holds all file paths and external URLs. It also defines `RUBRIC_TO_COLLEGE`, a dict that maps every course subject rubric (e.g. `ACCT`, `BIOL`) to its college code (`CBAC`, `CSHE`, etc.). The college codes and their full names are documented in a comment above the dict. When a new academic program is added, add its rubric here. When deploying or moving the project, the file paths at the top are the first things to check.

`config_terms.py` holds `SEMESTERS_LIST` — the list of `(term_code, display_name)` tuples that populate the term dropdown. Term codes follow the MinnState format: 4-digit year + 1-digit semester (`1`=Summer, `3`=Fall, `5`=Spring). Example: `20265` = Spring 2026.

### `scrape.py`

Standalone script that fetches course data from the MinnState registration site and writes CSV files to `data/`. Run it manually or via a cron job to collect new data. The output is passed to `update_data_table.py`.

### `update_data_table.py`

Takes a scraped CSV file, merges it into `all_enrollments.csv` and `all_enrollments.parquet`, rebuilds derived columns (Term, College, tuition formatting), and updates `config_terms.py` with any new term codes.

---

## Adding a new semester

1. Run the scraper for the new term code:
   ```bash
   python scrape.py --year-term <term-code>
   ```
2. Feed the output to the updater:
   ```bash
   python update_data_table.py data/<scraped-file>.csv
   ```
   This merges the new data, rebuilds the parquet file, and updates `config_terms.py` automatically.
3. Update `DEFAULT_TERM` in `config.py` to the new term's code and name.

These two steps are what `daily_update_script.sh` automates on a schedule: it activates the `headspace` conda environment, runs the scraper for each configured term, feeds each result into the updater, then commits `all_enrollments.csv`, `all_enrollments.parquet`, `config_terms.py`, and `config.py`, pushes to `origin`, and deploys with `git push dokku main`.

---

## Running locally

```bash
cp .env.example .env          # fill in SECRET_KEY at minimum
conda activate headspace      # or your own venv with requirements.txt installed
pip install -r requirements-dev.txt
flask --app app run
```

The app is deployed in production via [Dokku](https://dokku.com/) — `git push dokku main` builds and releases it using the buildpack and the `Procfile` (`web: gunicorn app:app --log-file=-`). There is no Docker or container tooling in this deployment; Dokku's buildpack handles the Python environment directly from `requirements.txt`.

---

## CSS architecture

All styles are imported in a single cascade through `static/css/app.css`:

```
tokens.css  →  base.css  →  shell.css  →  components/*  →  pages/*  →  utilities.css
```

Design tokens (colors, spacing, type scale) are defined as CSS custom properties in `foundation/tokens.css`. The MSUM brand colors are `--color-primary` (crimson `#c8102e`) and `--color-gold` (`#e8b800`). When adding styles, pick the most specific layer that applies — avoid adding page-specific rules to component files or vice versa.

---

## Credits

- Original version: [Matthew Craig](https://github.com/mwcraig/)
- Backend and Polars migration: [Juan Cabanela](https://web.mnstate.edu/cabanela/)
- Front-end redesign: [Natoli Tesgera](https://github.com/Natoli74)
- DataTables/Chart.js front-end integration and data pipeline improvements: [Laween Al-Sulaivany](https://github.com/laween-alsulaivany)

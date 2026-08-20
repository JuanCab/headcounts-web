import json
import logging
import os
import re
import sys
from pathlib import Path

from config import (
    CACHE_DIR,
    COURSE_DATA_SOURCE_URL,
    DEFAULT_TERM,
    PARQUET_DATA,
)
from config_terms import SEMESTERS_LIST
from flask import (
    Flask,
    Response,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_wtf import CSRFProtect
import polars as pl
from models import SearchForm
from utils import (
    filter_data,
    process_data_request,
    build_url,
    get_secret_key,
    get_analytics_data,
    _build_display_table,
    _display_text,
    _search_rows,
)

# Module-level parquet cache — re-read only when the file changes on disk
_parquet_cache = {'df': None, 'mtime': None}


def get_parquet():
    """Return cached parquet DataFrame, refreshing only if the file mtime changed."""
    try:
        mtime = os.path.getmtime(PARQUET_DATA)
    except FileNotFoundError:
        return None
    if _parquet_cache['df'] is None or _parquet_cache['mtime'] != mtime:
        _parquet_cache['df'] = pl.read_parquet(PARQUET_DATA)
        _parquet_cache['mtime'] = mtime
    return _parquet_cache['df']


def _load_filtered(subject, spec1=None, spec2=None):
    """Load, filter, and collect the parquet in one call. Returns (df, subj_text)."""
    lf, subj_text = filter_data(get_parquet().lazy(), subject, spec1, spec2)
    return lf.collect(), subj_text


app = Flask(__name__, static_folder="static", template_folder="templates")


app.config["SECRET_KEY"] = get_secret_key()
csrf = CSRFProtect(app)
app.url_map.strict_slashes = False


# Configure logging to output error messages to the console and set
# the logging level to ERROR to avoid cluttering the console with
# non-error messages
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)


@app.context_processor
def inject_source_url():
    """Make COURSE_DATA_SOURCE_URL available in all templates."""
    return dict(source_url=COURSE_DATA_SOURCE_URL)


@app.route("/", methods=["GET", "POST"])
def index():
    """
    Show the form (GET) or accept submission (POST) and redirect
    to the canonical /<subject>/<spec1>/<spec2> URL handled by filtered_view.
    """
    form = SearchForm()

    if request.method == "POST":
        if form.validate_on_submit():
            # Build URL and redirect to filtered_view (bookmarkable)
            dest = build_url(form)
            return redirect(dest)
        else:
            return render_template("search.html", form=form, default_term=DEFAULT_TERM)

    # GET (initial page or redirected after POST)
    return render_template("search.html", form=form, default_term=DEFAULT_TERM)


@app.route("/<subject>")
@app.route("/<subject>/<spec1>")
@app.route("/<subject>/<spec1>/<spec2>")
def filtered_view(subject, spec1=None, spec2=None):
    # Check if the subject is 'favicon.ico' and return an empty string
    # to avoid processing requests for the favicon
    if subject == "favicon.ico":
        return ""

    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    render_me, subj_text = _load_filtered(subject, spec1, spec2)
    return process_data_request(render_me, request.path, subj_text)


@app.route("/data/<subject>", methods=['GET', 'POST'])
@app.route("/data/<subject>/<spec1>", methods=['GET', 'POST'])
@app.route("/data/<subject>/<spec1>/<spec2>", methods=['GET', 'POST'])
@csrf.exempt
def data_view(subject, spec1=None, spec2=None):
    """Return filtered data in DataTables server-side processing format."""
    # Accept POST (to avoid gunicorn request-line length limit with many columns)
    # or GET for direct access. CSRF exempt: read-only endpoint, no state changes.
    params = request.form if request.method == 'POST' else request.args
    draw = int(params.get('draw', 1))
    start = int(params.get('start', 0))
    length = int(params.get('length', 100))
    search_value = params.get('search[value]', '').strip().lower()
    order_col_idx = int(params.get('order[0][column]', -1))
    order_dir = params.get('order[0][dir]', 'asc')

    render_me, _ = _load_filtered(subject, spec1, spec2)

    if render_me.is_empty():
        return Response(
            json.dumps({'draw': draw, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []}),
            mimetype='application/json'
        )

    columns, rows = _build_display_table(render_me)
    records_total = len(rows)

    if search_value:
        mask = _search_rows(rows, search_value)
        rows = [row for row, keep in zip(rows, mask) if keep]
    records_filtered = len(rows)

    if 0 <= order_col_idx < len(columns):
        def _sort_key(row):
            text = _display_text(row[order_col_idx])
            try:
                return (0, float(text.replace(',', '').replace('$', '')))
            except ValueError:
                return (1, text)
        rows.sort(key=_sort_key, reverse=(order_dir == 'desc'))

    page_rows = rows[start:] if length == -1 else rows[start:start + length]

    return Response(
        json.dumps({
            'draw': draw,
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': page_rows,
        }),
        mimetype='application/json'
    )


# Define the route for downloading a cached CSV file
# This route allows users to download a specific file from the cache
# The filename is passed as a parameter in the URL
@app.route("/download/<filename>")
def download(filename):
    # Thanks to this Stack Overflow answer for the idea of
    # using `send_from_directory` to serve files from a directory:
    # https://stackoverflow.com/questions/34009980/return-a-download-and-rendered-page-in-one-flask-response
    return send_from_directory(CACHE_DIR, filename)


@app.route("/analytics")
def analytics():
    """Render the analytics/overview dashboard page."""
    table = get_parquet()
    # Allow term selection via ?term=XXXXX; fall back to default
    try:
        selected_term = int(request.args.get('term', DEFAULT_TERM[0]))
    except (ValueError, TypeError):
        selected_term = DEFAULT_TERM[0]
    data = get_analytics_data(table, selected_term)
    return render_template(
        'analytics.html',
        analytics_data=data,
        summary=data['summary'],
        current_term_name=data['current_term_name'],
        current_term_code=data['current_term_code'],
        semesters=SEMESTERS_LIST,
    )


@app.route("/api/<subject>")
@app.route("/api/<subject>/<spec1>")
@app.route("/api/<subject>/<spec1>/<spec2>")
def api_view(subject, spec1=None, spec2=None):
    """
    Return filtered enrollment data as JSON.
    Accepts the same URL parameters as the main filtered_view.
    """
    result, _ = _load_filtered(subject, spec1, spec2)
    return Response(result.write_json(), mimetype='application/json')


@app.route("/csv/<subject>")
@app.route("/csv/<subject>/<spec1>")
@app.route("/csv/<subject>/<spec1>/<spec2>")
def csv_view(subject, spec1=None, spec2=None):
    """
    Return filtered enrollment data as a CSV file download.
    Accepts the same URL structure as /api/ plus an optional ?q= text search param.
    """
    result, _ = _load_filtered(subject, spec1, spec2)

    q = request.args.get('q', '').strip().lower()
    if q and not result.is_empty():
        # Build display rows so the search matches exactly what the user saw on screen
        _, display_rows = _build_display_table(result)
        result = result.filter(pl.Series(_search_rows(display_rows, q)))

    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', subject)
    return Response(
        result.write_csv(),
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment; filename={safe_name}.csv"}
    )


if __name__ == "__main__":
    app.run(debug=True)

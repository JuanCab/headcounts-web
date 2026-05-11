import json
import logging
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
    flash,
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
)

MAINTENANCE_FILE = Path('.maintenance')

app = Flask(__name__, static_folder="static", template_folder="templates")


app.config["SECRET_KEY"] = get_secret_key()
csrf = CSRFProtect(app)
app.url_map.strict_slashes = False


# Configure logging to output error messages to the console and set
# the logging level to ERROR to avoid cluttering the console with
# non-error messages
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)


@app.before_request
def check_site_status():
    """Block all non-static requests during data updates or when data is missing."""
    if request.path.startswith('/static'):
        return
    if MAINTENANCE_FILE.exists():
        return render_template('maintenance.html'), 503
    if not Path(PARQUET_DATA).exists() and request.endpoint not in ('index', None):
        return render_template('maintenance.html',
                               message="Data file is missing. Please run the data update script."), 503


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

    # Read the Parquet file containing course enrollment data as a lazy
    # Polars DataFrame. This allows for efficient querying without loading
    # the entire dataset into memory at once.
    table = pl.read_parquet(PARQUET_DATA).lazy()

    # Crate a directory for cached CSV files if it does not already exist.
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

    # Get a filtered version of the lazy DataFrame based on the subject
    # (including LASC, WI, or all courses).
    filtered_table, subj_text = filter_data(table, subject, spec1, spec2)

    # Collect the filtered DataFrame into a regular Polars DataFrame
    # to be rendered in the template.
    render_me = filtered_table.collect()

    # Call process_data_request to render the filtered data in the render_me
    # DataFrame and return the response. The request path is passed to
    # common_response to ensure the correct URL is used for the download link.
    # The subj_text is also passed to provide context for the subject
    # being viewed.
    return process_data_request(render_me, request.path, subj_text)


@app.route("/data/<subject>")
@app.route("/data/<subject>/<spec1>")
@app.route("/data/<subject>/<spec1>/<spec2>")
def data_view(subject, spec1=None, spec2=None):
    """Return processed table data as JSON for DataTables Ajax loading."""
    import json as _json
    # Load and filter the dataset the same way filtered_view does
    table = pl.read_parquet(PARQUET_DATA).lazy()
    filtered_table, _ = filter_data(table, subject, spec1, spec2)
    render_me = filtered_table.collect()
    # Return an empty DataTables-compatible payload if nothing matched
    if render_me.is_empty():
        return Response(_json.dumps({'columns': [], 'data': []}), mimetype='application/json')
    columns, rows = _build_display_table(render_me)
    return Response(
        _json.dumps({'columns': columns, 'data': rows}),
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
    table = pl.read_parquet(PARQUET_DATA)
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
    table = pl.read_parquet(PARQUET_DATA).lazy()
    filtered_table, _ = filter_data(table, subject, spec1, spec2)
    result = filtered_table.collect()
    return Response(result.write_json(), mimetype='application/json')


if __name__ == "__main__":
    app.run(debug=True)

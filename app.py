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
)

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
            flash("Please correct the errors below", "error")
            return render_template("search.html", form=form)

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


# Define the route for downloading a cached CSV file
# This route allows users to download a specific file from the cache
# The filename is passed as a parameter in the URL
@app.route("/download/<filename>")
def download(filename):
    # Thanks to this Stack Overflow answer for the idea of
    # using `send_from_directory` to serve files from a directory:
    # https://stackoverflow.com/questions/34009980/return-a-download-and-rendered-page-in-one-flask-response
    return send_from_directory(CACHE_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True)

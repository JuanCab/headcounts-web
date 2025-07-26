import logging
import os
import sys
from pathlib import Path

from config import CACHE_DIR, COURSE_DATA_SOURCE_URL, PARQUET_DATA
from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for
from flask_wtf import CSRFProtect
import polars as pl
from models import SearchForm
from utils import filter_data, filter_data_advanced, process_data_request

app = Flask(__name__, static_folder='static', template_folder='templates')

def get_secret_key():
    """
    Retrieve the Flask SECRET_KEY for session and CSRF protection.

    This function first attempts to get the secret key from the environment variable 'SECRET_KEY'.
    If the environment variable is not set, it falls back to reading the key from a local file named '.flask_secret_key'.
    This file should be excluded from version control (e.g., listed in .gitignore) to prevent accidental exposure of secrets.

    Raises:
        RuntimeError: If neither the environment variable nor the file is found, indicating that the secret key is missing.

    Returns:
        str: The secret key string to be used by Flask for cryptographic operations.

    Security Note:
        The secret key is required for securely signing session cookies and CSRF tokens.
        Never hardcode the secret key in source code or commit it to version control.
        Always use a strong, random value for production deployments.
    """
    # Try environment variable first
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    # Fallback: read from a file (not tracked by git)
    try:
        with open('.flask_secret_key') as f:
            return f.read().strip()
    except FileNotFoundError:
        raise RuntimeError("SECRET_KEY not set and .flask_secret_key file not found!")
    
app.config['SECRET_KEY'] = get_secret_key()
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

@app.route('/')
def index():
    """Redirect root URL to the search page."""
    return redirect(url_for('search'))

@app.route('/<subject>')
@app.route('/<subject>/<spec1>')
@app.route('/<subject>/<spec1>/<spec2>')
def filtered_view(subject, spec1=None, spec2=None):
    # Check if the subject is 'favicon.ico' and return an empty string
    # to avoid processing requests for the favicon
    if subject == 'favicon.ico':
        return ''

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

def build_url(form):
    """
    Build a clean /<college_or_subject>/<term>/<class_code> style URL.
    Priority:
      1) subject_or_college
      2) course_type (lasc, wi, 18online)
      3) semester/year (term)
      4) class_code
    """
    parts = []

    # 1) Subject or College
    target = (form.subject_or_college.data or "").strip().lower()
    if target:
        parts.append(target)

    # 2) Course Type (only if subject/college is NOT selected)
    else:
        ctype = (form.course_type.data or "").strip()
        if ctype:
            if ctype == "wi":
                parts.append("WI")
            elif ctype == "18":
                parts.append("18online")
            elif ctype.startswith("lasc/"):
                area = ctype.split("/", 1)[1]
                parts.extend(["LASC", area])

    # 3) Term (semester + year combined)
    term = None
    if form.semester.data and form.year.data:
        term_map = {'Spring': '5', 'Summer': '1', 'Fall': '3'}
        sem = form.semester.data
        yr = int(form.year.data)
        if sem == 'Spring':
            yr -= 1
        term = f"{yr}{term_map.get(sem, '')}"
        parts.append(term)

    # 4) Class code (if provided)
    if form.class_code.data:
        parts.append(form.class_code.data.strip())

    return "/" + "/".join(parts) if parts else "/"


@app.route('/search', methods=['GET'])
def search():
    """
    Display the search form or process the query (GET-only).
    Always redirect to the bookmarkable /<subject>/<spec1>/<spec2> URL.
    """
    form = SearchForm(request.args)

    # If there are query parameters (form submitted)
    if request.args:
        if form.validate():
            # Build URL and redirect to filtered_view
            dest = build_url(form)
            return redirect(dest)
        else:
            flash("Please correct the errors below", "error")

    # Initial load (no query parameters) or invalid form -> show form
    return render_template('search.html', form=form)




# Define the route for downloading a cached CSV file
# This route allows users to download a specific file from the cache
# The filename is passed as a parameter in the URL
@app.route('/download/<filename>')
def download(filename):
    # Thanks to this Stack Overflow answer for the idea of
    # using `send_from_directory` to serve files from a directory:
    # https://stackoverflow.com/questions/34009980/return-a-download-and-rendered-page-in-one-flask-response
    return send_from_directory(CACHE_DIR, filename)

if __name__ == '__main__':
    app.run(debug=True)

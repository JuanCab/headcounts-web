from pathlib import Path
import logging
import sys
import polars as pl

from flask import Flask, render_template, request, send_from_directory
from flask_bootstrap import Bootstrap

from config import CACHE_DIR, DATA_FILE
from utils import filter_data, common_response

# Set up the Flask application to allow URLs that end in slash to be
# treated the same as those that do not.
app = Flask(__name__)
app.url_map.strict_slashes = False

# Set up the Flask-Bootstrap extension to use Bootstrap for styling.
bootstrap = Bootstrap(app)

# Configure logging to output error messages to the console and set
# the logging level to ERROR to avoid cluttering the console with 
# non-error messages
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)

# Define the route for the root URL of the application This route serves
# the instructions page when the user accesses the root URL It renders
# the 'instructions.html' template, which contains information on how to
# use the application
@app.route('/')
def index():
    base_url = request.url_root
    return render_template('instructions.html', 
                           base_url=base_url)


# Define the route for the /<subject>/<spec1>/<spec2> URL pattern This
# route handles requests for specific subjects and specifications It can
# accept up to two specifications (spec1 and spec2) after the subject
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
    table = pl.read_parquet(DATA_FILE).lazy()

    # Crate a directory for cached CSV files if it does not already exist.
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

    # Get a filtered version of the lazy DataFrame based on the subject
    # (including LASC, WI, or all courses).
    filtered_table, subj_text = filter_data(table, subject, spec1, spec2)

    # Collect the filtered DataFrame into a regular Polars DataFrame
    # to be rendered in the template.
    render_me = filtered_table.collect()

    # Call common_response to render the filtered data in the render_me
    # DataFrame and return the response. The request path is passed to
    # common_response to ensure the correct URL is used for the download link.
    # The subj_text is also passed to provide context for the subject 
    # being viewed.
    return common_response(render_me, request.path, subj_text)


# Define the route for downloading a cached CSV file
# This route allows users to download a specific file from the cache
# The filename is passed as a parameter in the URL
@app.route('/download/<filename>')
def download(filename):
    # Thanks to this Stack Overflow answer for the idea of
    # using `send_from_directory` to serve files from a directory:
    # https://stackoverflow.com/questions/34009980/return-a-download-and-rendered-page-in-one-flask-response
    return send_from_directory(CACHE_DIR, filename)


# Define the application entry point
if __name__ == '__main__':
    app.run(debug=True)

from pathlib import Path
import logging
import re

import polars as pl

from flask import Flask, render_template, request, send_from_directory
from flask_bootstrap import Bootstrap

from config import CACHE_DIR, DATA_FILE
from utils import filter_subject, common_response

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
def subtable_spec(subject, spec1=None, spec2=None):
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
    subject = subject.lower()
    filtered_table = filter_subject(subject, table)

    # Collect the specifiers (spec1 and spec2) into a list (lowercased)
    specs = [spec1, spec2]
    # If spec1 or spec2 is 'all', replace it with None to simplify filtering.
    specs = [s.lower() if s.lower() != 'all' else None for s in specs]
    # Now filter out any None values from the specs list.
    specs = [s for s in specs if s is not None]
    # If no specific specs are provided and the subject is not 'all',
    # filter to only include the most recent year/term.
    if not specs and subject != 'all':
        # Identify the most recent year/term in the dataset.
        most_recent = ( filtered_table.select(pl.col("Fiscal yrtr").max())
                 .collect()
                 .item()
                 )
        # Filter the DataFrame to include only rows with the most recent
        # year/term.
        filtered_table = filtered_table.filter(
            pl.col("Fiscal yrtr") == most_recent
        )
    else:
        # Check specifiers (which should be lowercased) and filter the
        # DataFrame accordingly.
        for spec in specs:
            # Process each specifier to filter the DataFrame.
            if len(spec) == 5 and spec[-1] in ['1', '3', '5']:
                # Specifier probably a year/term, filter by it:
                filtered_table = filtered_table.filter(
                    pl.col('Fiscal yrtr') == spec
                    )
            elif (re.match('[a-z]{2,4}', spec) and spec not in ['lasc', 'wi']):
                # Specifier is probably a course rubric, filter by it:
                filtered_table = filtered_table.filter(
                    pl.col('Subj') == spec.upper()
                )
            else:
                # Specifier either a course number or LASC area
                if subject == 'lasc':
                    # If the subject is 'lasc', filter by LASC/WI value
                    filtered_table = filtered_table.filter(
                        pl.col('LASC/WI').str.contains(spec, case=False)
                    )
                else:
                    # Otherwise, filter by course number
                    filtered_table = filtered_table.filter(
                        pl.col('#') == spec
                    )

    # Collect the filtered DataFrame into a regular Polars DataFrame
    # to be rendered in the template.
    render_me = filtered_table.collect()

    return common_response(render_me, request.path)


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

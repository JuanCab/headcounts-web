from pathlib import Path
import logging
import sys
import polars as pl
import os

from flask import Flask, render_template, request, send_from_directory, flash, redirect, url_for
from flask_wtf import CSRFProtect

from config import CACHE_DIR, PARQUET_DATA, COURSE_DATA_SOURCE_URL
from utils import filter_data, process_data_request, filter_data_advanced
from models import SearchForm

# Set up the Flask application to allow URLs that end in slash to be
# treated the same as those that do not.
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-key')
csrf = CSRFProtect(app)
app.url_map.strict_slashes = False


# Configure logging to output error messages to the console and set
# the logging level to ERROR to avoid cluttering the console with 
# non-error messages
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)

# Content processor for sourse URL
# This makes the COURSE_DATA_SOURCE_URL variable available in all
# templates without having to pass it explicitly each time
@app.context_processor
def inject_source_url():
    return dict(source_url=COURSE_DATA_SOURCE_URL)

# Define the route for the root URL of the application This route serves
# the instructions page when the user accesses the root URL It renders
# the 'instructions.html' template, which contains information on how to
# use the application
@app.route('/')
def index():
    return redirect (url_for('search'))


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

# @app.route('/', methods=['GET', 'POST'])
@app.route('/search', methods=['GET', 'POST'])
def search():
    # This route handles the search functionality. It allows users to
    # search for courses based on a query string.
    
    # If the request method is POST, it means the user has submitted a search
    # query. The query is extracted from the form data.
    form = SearchForm()
    if request.method == 'POST':
        filters = {}
        if form.validate_on_submit():
            # If the form is valid, extract the filters from the form data.
            if not form.has_filters():
                filters['all_courses'] = True
            else:
                if form.colleges.data:
                    filters['college'] = form.colleges.data
                if form.subjects.data:
                    filters['subject'] = form.subjects.data
                if form.class_code.data:
                    filters['course_number'] = form.class_code.data
                if form.lasc_number.data:
                    filters['lasc_area'] = form.lasc_number.data
                if form.semester.data and form.year.data:
                    term_map = {'Spring': '5', 'Summer': '1', 'Fall': '3'}
                    if form.semester.data in term_map and form.year.data:
                        year = int(form.year.data)
                        term_digit = term_map[form.semester.data]
                        # For Spring, subtract 1 from the year
                        if form.semester.data == 'Spring':
                            year -= 1
                        filters['term'] = int(str(year) + term_digit)
                if form.writing_intensive.data:
                    filters['wi_only'] = True
                if form.online_18.data:
                    filters['online_only'] = True
                
                

            # Read the Parquet file containing course enrollment data as a lazy
            # Polars DataFrame.
            table = pl.read_parquet(PARQUET_DATA).lazy()

            # Filter the data based on the search query.
            filtered_table, subj_text = filter_data_advanced(table, **filters)

            # Collect the filtered DataFrame into a regular Polars DataFrame.
            results = filtered_table.collect()

            return process_data_request(results, request.path, subj_text)
        else:
            # Form validation failed
            flash("Please correct the errors below", "error")
            return render_template('search.html', form=form)

    # If the request method is GET, render the search page without results.
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


# Define the application entry point
if __name__ == '__main__':
    app.run(debug=True)

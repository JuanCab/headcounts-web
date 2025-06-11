import os
import logging
import sys
import re

import numpy as np
from astropy.table import Table, Column

from flask import Flask, render_template, request, send_from_directory
from flask_bootstrap import Bootstrap

from config import CACHE_DIR
from utils import parse_year_term, match_subject, common_response

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

# Read the CSV file containing course enrollment data, used masked=True
# to allow for masking of missing values.
table_orig = Table.read('all_enrollments.csv', format='ascii.csv')
table = Table(table_orig, masked=True)
table.sort(['year_term', 'Subj', '#'])

# Attempt to create the cache directory if it does not already exist
# otherwise, ignore the error if it already exists
try:
    os.mkdir(CACHE_DIR)
except OSError:
    pass

# Compute and add a human-readable year-term column to astropy Table
human_yrtr = [parse_year_term(str(yrtr)) for yrtr in table['year_term']]
human_yrtr = Column(data=human_yrtr, name='Term')
table.add_column(human_yrtr, index=0)


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
    render_me = match_subject(subject, table)
    specs = [spec1, spec2]
    specs = [s for s in specs if s is not None]
    if not specs and subject != 'all':
        terms = sorted(set(render_me['year_term']))
        most_recent = terms[-1]
        keep = render_me['year_term'] == most_recent
        render_me = render_me[keep]
    else:
        for spec in specs:
            if spec != 'all':
                if len(spec) == 5 and spec[-1] in ['1', '3', '5']:
                    # spec probably a year/term, filter by it:
                    keep = render_me['year_term'] == int(spec)
                elif (re.match('[a-z]{2,4}', spec.lower()) and
                      spec.lower() not in ['lasc', 'wi']):
                    # spec is probably a course rubric, filter by it:
                    keep = render_me['Subj'] == spec.upper()
                else:
                    # Assume it was a course number or LASC area
                    if subject == 'lasc':
                        keep = np.array([spec in l for l in render_me['LASC/WI']])
                    else:
                        keep = render_me['#'] == str(spec)

                render_me = render_me[keep]

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

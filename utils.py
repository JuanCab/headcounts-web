import datetime
import os
import re

import numpy as np
from flask import render_template
import polars as pl

from config import COURSE_DETAIL_URL, CACHE_DIR

#
# This is an importable file of utility functions for the Flask app.
# The only functions that actually get imported int the app are
# filter_subject and common_response.  All the other functions here
# are used by those two functions to do the actual work of filtering
# the data and calculating various statistics.
#

def filter_data(tbl, subject, spec1=None, spec2=None):
    """
    This takes the original Polars Lazy DataFrame and filters it down to
    only the rows that match the subject and specifications provided.
    The subject can be a course subject (e.g., 'CSCI'), a LASC area
    ('lasc'), a WI course ('wi'), or '18online' for online courses. If
    the subject is 'all', it returns the entire table.

    Parameters
    ----------
    tbl : polars Lazy DataFrame
        The table containing course data to be filtered.

    subject : str
        The subject to filter by, which can be a course subject (e.g.,
        'CSCI'), a LASC area ('lasc'), a WI course ('wi'), or '18online'
        for online courses. Setting it to 'all' will return the
        entire table without filtering (pending other specified filters
        below).

    spec1 : str, optional
        The first specification to filter by, which can be a course
        number, a LASC area, a WI course, or term code. If not provided,
        it defaults to None.

    spec2 : str, optional
        The second specification to filter by, which can be a course
        number, a LASC area, a WI course, or term code. If not provided,
        it defaults to None.

    Returns
    -------
    polars Lazy DataFrame
        This is a Polars LazyFrame, which applies the filtering
        operation lazily, meaning it does not immediately execute the
        filtering operation until the data is actually needed.


    The default behavior is to filter by the subject provided. If
    the subject is 'lasc', it filters for LASC courses; if 'wi', it
    filters for WI courses; if '18online', it filters for online
    courses; if 'all', it returns the entire table; otherwise, it
    filters by the specified course subject.
    """

    # Make sure subject is lowercase
    subject = subject.lower()

    # Determine the subject category and filter accordingly
    if subject == 'lasc':
        return tbl.filter(
            (pl.col("LASC/WI").is_not_null()) & (pl.col("LASC/WI") != "WI")
            )
    elif subject == 'wi':
        filtered_table = tbl.filter(pl.col("LASC/WI") == "WI")
    elif subject == '18online':
        filtered_table = tbl.filter(pl.col('18online') == True)
    elif subject == 'all':
        # No filtering, just return the original LazyFrame
        filtered_table = tbl
    else:
        # Regular academic subject to select
        filtered_table = tbl.filter(pl.col('Subj') == subject.upper())

    # Collect the specifiers (spec1 and spec2) into a list (lowercased)
    # after filtering out 'all' and Nones
    specs = [s.lower() for s in [spec1, spec2] if s and s.lower() != 'all']

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
            # Process each specifier to filter the Lazy DataFrame.
            # 1) Handle year/term specifiers
            if len(spec) == 5 and spec[-1] in ['1', '3', '5']:
                filtered_table = filtered_table.filter(
                    pl.col('Fiscal yrtr') == int(spec)
                    )
            # 2) Handle Course Rubric specifiers
            elif (re.match('[a-z]{2,4}', spec) and spec not in ['lasc', 'wi']):
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

    # Return the filtered LazyFrame
    return filtered_table


def filled_credits(credit_column, variable_credits=1):
    """
    Convert the course credit column in the table to a numeric format,
    filling in variable credits with a specified value.

    Parameters
    ----------
    credit_column : Polars Series
        The column containing credit information, which may include
        variable credits represented as 'Vari.'.
    variable_credits : int, optional
        The value to use for variable credits, by default 1.

    Returns
    ------- 
    list of int
        This function returns a list of integers representing the
        credits for each course. Variable credits (represented as 'Vari.')
        in the original column are replaced with the specified value
        (`variable_credits`), and all credits are rounded to the nearest
        valid integer.
    """
    # Identify rows in Polars series where the credit value is 'Vari.'
    vari_rows = credit_column == 'Vari.'

    # Create a copy of the credit column, masking the variable rows
    # and filling them with the specified variable credits value
    crds = credit_column.copy()
    crds.mask[vari_rows] = True
    crds.fill_value = variable_credits

    # Convert the filled column to float, round it, and then convert
    # to int
    crds = np.round(crds.filled().astype(float)).astype(int)
    return crds


def calc_sch(table, vari_credits=1):
    """
    Calculate total student credit hours generated by courses in this 
    table.

    Parameters
    ----------
    table : astropy Table
        The table containing course data, including 'Crds' and 'Enrolled'
        columns.
    vari_credits : int, optional
        The value to use for variable credits, by default 1.

    Returns
    -------
    int
        The total student credit hours (SCH) calculated as the sum of
        enrolled students multiplied by their respective credits.
    """

    # Fill the 'Crds' column with variable credits where applicable
    crds = filled_credits(table['Crds'], variable_credits=vari_credits)

    # Calculate the total student credit hours by multiplying
    # the number of enrolled students by their respective credits
    # and summing the results
    sch = (table['Enrolled'] * crds).sum()

    return sch


def calc_seats(table):
    """
    Calculate the number of seats that are available, filled, empty, for
    classes that are not canceled.

    Parameters
    ----------
    table : astropy Table
        The table containing course data, including 'Status', 'Size:',
        and 'Enrolled' columns.

    Returns
    -------
    dict
        A dictionary containing the number of empty seats, filled seats,
        and available seats in the courses that are not canceled.
        The keys are 'empty', 'filled', and 'available'.
    """

    # Filter out canceled courses
    not_canceled = table['Status'] != 'Cancelled'

    # Calculate the number of empty seats for courses that are not canceled
    # and where the size is greater than the number of enrolled students.
    empty = table['Size:'] - table['Enrolled']

    # Only keep positive empty seats
    positive = empty > 0
    empty *= positive

    # Sum the empty, filled, and available seats for courses that are 
    # not canceled
    empty = empty[not_canceled].sum()
    available = table['Size:'][not_canceled].sum()
    filled = table['Enrolled'][not_canceled].sum()
    return {'empty': empty, 'filled': filled, 'available': available}


def calc_tuition(table, variable_credits=1):
    """
    Calculate the tuition revenue generated by the courses in the
    table.

    Parameters
    ----------
    table : astropy Table
        The table containing course data, including 'Tuition unit',
        'Crds', 'Tuition -resident', and 'Enrolled' columns.
    variable_credits : int, optional
        The value to use for variable credits, by default 1.

    Returns
    -------
    float
        The total tuition revenue calculated as the sum of enrolled
        students multiplied by their respective tuition amounts, adjusted
        for credit hours if applicable.
    """
    by_credit = table['Tuition unit'] == 'credit'
    credits = filled_credits(table['Crds'],
                             variable_credits=variable_credits)
    tuition_nas = table['Tuition -resident'] == 'n/a'
    table['Tuition -resident'].mask |= tuition_nas
    # parse tuition as a string into a number
    money = [float(m.replace('$', '').replace(',', '')) for m in table['Tuition -resident'].filled(fill_value='0')]
    money *= table['Enrolled']
    money[by_credit] *= credits[by_credit]
    return money.sum()


def gen_cache_file(path, table):
    """
    Generate a name for a cache of a view of the data based on
    the URL path to the view

    Parameters
    ----------
    path : str
        The URL path that got the user here, used to generate a unique
        filename for the cached data.
    table : astropy Table
        The table containing course data to be cached.

    Returns
    -------
    str
        The name of the cached file, which is a CSV file containing the
        course data for the specified view.
    """

    # Compute the average time for all courses in the table.
    avg_time = int(table['timestamp'].mean())

    # path always starts with a leading /, remove it
    rel_path = path[1:]
    parts = rel_path.split('/')
    parts.extend([str(avg_time)])
    name = '-'.join(parts) + '.csv'
    file_path = os.path.join(CACHE_DIR, name)
    if not os.path.isfile(file_path):
        table.write(file_path)
    return name


def common_response(render_me, path):
    """
    Most of what we are returning is the same for all views,
    we just have a bunch of routes for getting there.

    Parameters
    ----------
    render_me : astropy Table
        The table to be rendered in the view.

    path : str
        The URL path that got the user here.

    Returns
    -------
    str
        The rendered HTML template for the course information page,
        including the table, timestamp, most recent term, year terms,
        cache file name, student credit hours, available seats, and
        tuition revenue.
    """
    terms = sorted(set(render_me['year_term']))
    year_terms = ', '.join([parse_year_term(str(t)) for t in terms])
    file_name = gen_cache_file(path, render_me)
    most_recent = int(render_me['timestamp'].max())
    most_recent = datetime.datetime.fromtimestamp(most_recent)
    oldest = render_me['timestamp'].min()
    return render_template('course_info.html', table=render_me,
                           timestamp=int(render_me['timestamp'].mean()),
                           most_recent=most_recent,
                           year_term=year_terms,
                           sch=calc_sch(render_me),
                           filename=file_name,
                           seats=calc_seats(render_me),
                           revenue=calc_tuition(render_me),
                           base_detail_url=COURSE_DETAIL_URL)

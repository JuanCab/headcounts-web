import datetime
import re
from pathlib import Path

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

    Parameters
    ----------
    tbl : polars Lazy DataFrame
        The table containing course data to be filtered.

    subject : str
        The subject to filter by, which can be a course subject (e.g.,
        'CSCI'), a 4-letter MSUM college code (valid codes are 'CBAC',
        'COAH', 'CSHE', 'CEHS', or 'NONE'), a LASC area ('lasc'), a WI
        course ('wi'), or '18online' for online courses. Setting it to
        'all' will return the entire table without filtering (pending
        other specified filters below).

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

    The default behavior is to filter by the subject provided.
    - If the subject is a college code, it filters by college;
    - If the subject is 'lasc', it filters for LASC courses;
    - if 'wi', it filters for WI courses;
    - if '18online', it filters for online courses;
    - if 'all', it returns the entire table;
    otherwise, it filters by the specified course subject.
    """

    # MSUM Colleges
    MSUM_COLLEGES = [ 'cbac', 'coah', 'cshe', 'cehs', 'none' ]

    # Make sure subject is lowercase
    subject = subject.lower()

    # Determine the subject category and filter accordingly
    if subject in MSUM_COLLEGES:
        # If the subject is a college code, filter by that college
        filtered_table = tbl.filter(pl.col('College')== subject.upper())
    elif subject == 'lasc':
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

    # Always sort the output by Fiscal yrtr, Subj, #, and section
    filtered_table = filtered_table.sort(
        by=['Fiscal yrtr', 'Subj', '#', 'Sec'],
        descending=[False, False, False, False]
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
    Polars Series
        This function returns a Polars Series of integers representing
        the credits for each course. Variable credits (represented as
        'Vari.') in the original column are replaced with the specified
        value (`variable_credits`), and all credits are rounded to the
        nearest valid integer.
    """
    # Create a float version of the column, replacing 'Vari.' with the
    # specified variable credits value. Convert the float version into
    # a series of integers by ROUNDING to the nearest integer.
    result = (
        credit_column.str.replace("Vari\\.", "1")
        .cast(pl.Float64, strict=False)
    ).round(0).cast(pl.Int64).alias('IntCrd')

    # Return the column as rounded integers, converted to a numpy array
    return result


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
    crds = filled_credits(table['Credits'], variable_credits=vari_credits)

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
    table : polars DataFrame
        The table containing course data, including 'Credits', 'Enrolled',
        'Tuition unit', and 'Tuition Resident' columns.
    variable_credits : int, optional
        The value to use for variable credits, by default 1.

    Returns
    -------
    float
        The total tuition revenue calculated as the sum of enrolled
        students multiplied by their respective tuition amounts, adjusted
        for credit hours if applicable.
    """

    # NOTE: We used to mask "n/a" tuition values, but now they are set
    # to zero, which results in the same effect.

    # Create a Polars series of credits, filling in variable credits
    # filled with the specified value with "Vari." credit is set
    credits = filled_credits(table["Credits"],
                             variable_credits=variable_credits)
    # Add this series to the table as a new column
    table = table.with_columns(credits.alias('Integer Credits'))

    # The unit for tuition can either be 'course' or 'credit'. So to
    # compute the total tuition, we need to add up all the tuition
    # values for each course, multiplied by the number of enrolled
    # students, and then multiply by the number of credits for each
    # course if the unit is 'credit'. If the unit is 'course', we just
    # multiply by the number of enrolled students. We will assume
    # residential tuition for now.
    table = table.with_columns(
        # Tuition by course
        pl.when(pl.col("Tuition unit") == "course")
        .then(pl.col("Tuition Resident") * pl.col("Enrolled"))
        # Tuition by credit
        .otherwise(pl.col("Tuition Resident") * pl.col("Integer Credits")
                   * pl.col("Enrolled"))
        .alias("Tuition Charged")
    )

    # Return calculated tuition revenue by summing the 'Tuition Charged'
    return table['Tuition Charged'].sum()


def generate_csv_file(table, path, dir=CACHE_DIR):
    """
    Generate a CSV file containing all the data in this dataframe
    and save it to the cache directory. The filename is generated
    based on the URL path and the average timestamp of the courses in
    the table. The average timestamp is used to ensure that the filename
    is unique for each view, even if the same path is accessed multiple
    times.

    Parameters
    ----------
    table : polars Dataframe
        The polars dataframe containing course data to be cached.
    path : str
        The URL path that got the user here, used to generate a unique
        filename for the cached data.
    dir : str, optional
        The directory where the CSV file will be saved. Defaults to
        the CACHE_DIR defined in the config.

    Returns
    -------
    str
        The name of the CSV datafile containing the course data for the
        specified view.
    """

    # Compute the average time for all courses in the dataframe based
    # on the "Last Updated" column.
    avg_time = int(table.select(pl.col('Last Updated')).mean().item().timestamp())

    # path always starts with a leading /, remove it
    rel_path = path[1:]
    parts = rel_path.split('/')
    parts.append(str(avg_time))
    name = '-'.join(parts) + '.csv'
    file_path = Path(CACHE_DIR) / name

    # Check if file already exists, if not, write the dataframe to a
    # CSV file
    if not file_path.is_file():
        table.write_csv(file_path)

    # Return the name of the CSV file
    return name


def common_response(render_me, path):
    """
    Most of what we are returning is the same for all views,
    we just have a bunch of routes for getting there.

    Parameters
    ----------
    render_me : polars DataFrame
        The table to be rendered in the view.

    path : str
        The URL path that got the user here.


    Returns
    -------
    str
        The rendered HTML template for the course information page.

    This functions processes the provided Polars DataFrame of course
    data, calculates various statistics such as student credit hours,
    available seats, and tuition revenue, and then renders an HTML
    template with this information.

    It also generates a cached CSV file of the data for download.
    """

    # Determine all the unique 'Term' in this polars Dataframe, sorted
    # by Fiscal year/term,
    terms = (
        render_me.sort('Fiscal yrtr')
        .select(pl.col('Term'))
        .unique()
        .to_series()
        .to_list()
    )

    # Generate the CSV file corresponding to this data using full
    # dataset
    csv_filename = generate_csv_file(render_me, path)

    # Get most recent and oldest timestamps from the DataFrame
    most_recent = render_me.select(pl.col('Last Updated')).max().item()
    oldest = render_me.select(pl.col('Last Updated')).min().item()

    # If the table is larger than 100 rows, only render the first 100
    # rows to avoid performance issues in the browser.
    max_rows = 100
    if render_me.height > max_rows:
        render_me = render_me.head(max_rows)

    # Render the page using the 'course_info.html' template,
    return render_template('course_info.html',
                           table=render_me,
                           timestamp=int(render_me['timestamp'].mean()),
                           oldest=oldest,
                           max_rows=max_rows,
                           most_recent=most_recent,
                           year_term=terms,
                           sch=calc_sch(render_me),
                           filename=csv_filename,
                           seats=calc_seats(render_me),
                           revenue=calc_tuition(render_me),
                           base_detail_url=COURSE_DETAIL_URL)

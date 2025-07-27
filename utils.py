import re
from pathlib import Path

from config import CACHE_DIR, COURSE_DETAIL_URL
from flask import render_template
from great_tables import GT, html, loc, style
import numpy as np
import polars as pl
import xlsxwriter

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

    str
       A string representation of the subject and specifications that
       produced this filtered table.
    """

    # MSUM Colleges
    MSUM_COLLEGES = [ 'cbac', 'coah', 'cshe', 'cehs', 'none' ]

    # Set the subject description string to the upper case version
    # of the subject, but then make sure to convert the subject
    # to lower case for filtering purposes.
    subj_text = subject.upper()
    subject = subject.lower()

    # Determine the subject category and filter accordingly
    if subject in MSUM_COLLEGES:
        # If the subject is a college code, filter by that college
        filtered_table = tbl.filter(pl.col('College')== subject.upper())
    elif subject == 'lasc':
        filtered_table = tbl.filter(
            (pl.col("LASC/WI").is_not_null()) & (pl.col("LASC/WI") != "WI")
            )
    elif subject == 'wi':
        filtered_table = tbl.filter(pl.col("LASC/WI").str.contains("WI"))
    elif subject == '18online':
        filtered_table = tbl.filter(pl.col('18online') == True)
    elif subject == 'all':
        # No filtering, just return the original LazyFrame
        filtered_table = tbl
        subj_text = "All"
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
        # year/term if most_recent is not None.
        if most_recent is not None:
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
            # 2) Handle Course Prefix specifiers
            elif (re.match('[a-z]{2,4}', spec) and spec not in ['lasc', 'wi']):
                filtered_table = filtered_table.filter(
                    pl.col('Subj') == spec.upper()
                )
                subj_text = f"{subj_text} {spec}"
            elif subject == 'lasc':
                    # If the subject is 'lasc', filter by LASC/WI value
                    # which is expected to be uppercase (eg. 1A)
                    filtered_table = filtered_table.filter(
                        pl.col('LASC/WI').str.contains(spec.upper())
                    )
                    subj_text = f"{subj_text} {spec.upper()}"
            else:
                # Otherwise, filter by course number

                # If the last character is an underscore, treat it
                # as a wildcard and match any course number that
                # starts with the given numerical code.
                if spec[-1] == '_':
                    numcode = spec[:-1]
                    filtered_table = filtered_table.filter(
                        pl.col('#').str.starts_with(numcode.upper())
                    )
                    subj_text = f"{subj_text} {numcode.upper()} (Any Variant)"
                else: # Exact match of course number/letter
                    filtered_table = filtered_table.filter(
                        pl.col('#') == spec.upper()
                    )
                    subj_text = f"{subj_text} {spec.upper()}"


    # Always sort the output by Fiscal yrtr, Subj, #, and section
    filtered_table = filtered_table.sort(
        by=['Fiscal yrtr', 'Subj', '#', 'Sec'],
        descending=[False, False, False, False]
    )

    # Return the filtered LazyFrame and the subject text
    return (filtered_table, subj_text)


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


def calc_sch(table, variable_credits=1):
    """
    Calculate total student credit hours generated by courses in this
    table.

    Parameters
    ----------
    table : Polars dataframe
        The table containing course data, including 'Credits' and
        'Enrolled' columns.
    variable_credits : int, optional
        The value to use for variable credits, by default 1.

    Returns
    -------
    int
        The total student credit hours (SCH) calculated as the sum of
        enrolled students multiplied by their respective credits.
    """

    # Create a Polars series of credits, filling in variable credits
    # filled with the specified value with "Vari." credit is set
    credits = filled_credits(table["Credits"],
                             variable_credits=variable_credits)
    # Add this series to the table as a new column
    table = table.with_columns(credits.alias('Integer Credits'))

    # Calculate the total student credit hours by multiplying the number
    # of enrolled students ('Enrolled') by their respective credits and
    # summing the results
    sch = table.select(
        (pl.col('Enrolled') * pl.col('Integer Credits')).sum().alias('SCH')
    ).sum().item()

    return sch


def calc_seats(table):
    """
    Calculate the number of seats that are available, filled, empty, for
    classes that are not canceled.

    Parameters
    ----------
    table : Polars dataframe
        The table containing course data, including 'Status', 'Size',
        and 'Enrolled' columns.

    Returns
    -------
    dict
        A dictionary containing the number of empty seats, filled seats,
        and available seats in the courses that are not canceled.
        The keys are 'empty', 'filled', and 'available'.
    """

    # Filter out canceled courses from the Polars DataFrame
    table = table.filter(pl.col('Status') != 'Cancelled')

    # Calculate the number of empty seats for courses that are not canceled
    # and where the size is greater than the number of enrolled students.
    # If the number of empty seats is negative, set it to zero.
    table = table.with_columns(
        pl.when(pl.col('Size') - pl.col('Enrolled') < 0)
        .then(0)
        .otherwise(pl.col('Size') - pl.col('Enrolled'))
        .alias('Empty Seats')
    )

    # Sum the empty, filled, and available seats for courses that are
    # not canceled
    empty = table['Empty Seats'].sum()
    available = table['Size'].sum()
    filled = table['Enrolled'].sum()

    # Return a dictionary with the calculated values
    return {'empty': empty, 'filled': filled, 'available': available}


def calc_tuition(table, variable_credits=1):
    """
    Calculate the tuition revenue generated by the courses in the
    table assuming residential tuition for all students.

    Parameters
    ----------
    table : polars DataFrame
        The table containing course data, including 'Credits', 'Enrolled',
        'Tuition unit', and 'Tuition Resident' columns.
    variable_credits : int, optional
        The value to use for the number of credits per student for any
        variable credit courses, by default 1.

    Returns
    -------
    str
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
    return f"${table['Tuition Charged'].sum():,.2f}"


def generate_datafiles(table, path, subj_text, dir=CACHE_DIR):
    """
    Generates a CSV file and an Excel file containing all the data in
    this dataframe and save it to the cache directory. The filename is
    generated based on the subject text and the average timestamp of the
    courses in the table. The average timestamp is used to ensure that
    the filename is unique for each view, even if the same path is
    accessed multiple times.
    """
    # Compute the average time for all courses in the dataframe based
    # on the "Last Updated" column and format it as a string
    # representation of the average time in the format YYYYMMDD-HHMMSS.
    avg_time = table.select(pl.col('Last Updated')).mean().item().strftime("%Y%m%d-%H%M%S")

    # Fix "Last Updated" column to be a datetime column without the
    # timezone information, so it can be written to the CSV and Excel
    # files without issues.
    table = table.with_columns(
        pl.col("Last Updated")
        .dt.convert_time_zone("America/Chicago")
        .cast(pl.Datetime)
        .alias("Last Updated")
    )

    # Use a sanitized version of subj_text for the filename
    safe_subj_text = sanitize_excel_sheetname(subj_text).replace(" ", "_")
    # Optionally, you can further clean up the string if needed

    # Compose the filename
    filename_base = f"{safe_subj_text}-{avg_time}"

    csv_file = f"{filename_base}.csv"
    csv_path = Path(CACHE_DIR) / csv_file

    # Check if files already exist, if not, write the dataframe to both
    # CSV and Excel files.
    if not csv_path.is_file():
        table.write_csv(csv_path)

    # Define formatting and other information for the Excel file
    excel_file = f"{filename_base}.xlsx"
    excel_path = Path(CACHE_DIR) / excel_file
    table.write_excel(excel_path, worksheet=sanitize_excel_sheetname(subj_text))

    # Return the names of the files
    return csv_file, excel_file



def process_data_request(render_me, path, subj_text):
    """
    This processes the provided Polars DataFrame of course data,
    calculates various statistics such as student credit hours,
    available seats, and tuition revenue, and then renders an HTML
    template with this information.

    Parameters
    ----------
    render_me : polars DataFrame
        The table to be rendered in the view.

    path : str
        The URL path that got the user here.

    subj_text : str
        The description of the filtering applied to the table.

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

    # Check for an empty DataFrame, if so, return a custom response
    if render_me.is_empty():
        return render_template('results.html', subject=subj_text, n_rows=0)

    # Determine all the unique 'Term' in this polars Dataframe, sorted
    # by Fiscal year/term,
    terms = (
        render_me.sort('Fiscal yrtr')
        .unique('Fiscal yrtr')
        .select(pl.col('Term'))
        .to_series()
        .to_list()
    )

    # Modify subject text to include the range of terms
    if len(terms) > 1:
        # If there are multiple terms, show the first and last terms
        subj_text = f"{subj_text} Data for {terms[0]} through {terms[-1]}"
    else:
        # If there is only one term, just show that term
        subj_text = f"{subj_text} \n Data for {terms[0]}"

    # Get most recent and oldest timestamps from the DataFrame
    # to display in the rendered template.
    most_recent_dt = render_me.select(pl.col('Last Updated')).max().item()
    most_recent = most_recent_dt.strftime("%I:%M:%S %p on %B %d, %Y")
    # Get the oldest timestamp, which is the minimum of the 'Last Updated'
    # column.
    oldest_dt = render_me.select(pl.col('Last Updated')).min().item()
    if most_recent_dt.date() == oldest_dt.date():
        # If the oldest is on the same day as the most recent, just show
        # the time.
        oldest = oldest_dt.strftime("%I:%M:%S %p")
    else:
        # Otherwise, show the full date and time.
        oldest = oldest_dt.strftime("%I:%M:%S %p on %B %d, %Y")

    # Generate the CSV file corresponding to this data using full
    # dataset
    csv_filename, excel_filename = generate_datafiles(render_me, path, subj_text)

    # Compute various statistics for the table
    stu_credit_hours = calc_sch(render_me)
    seats = calc_seats(render_me)
    calulcated_tuition = calc_tuition(render_me)

    #
    # Modify the table to be rendered in the template
    #

    # If the table is larger than max_rows rows, only render the first max_rows
    # rows to avoid performance issues in the browser.
    max_rows = 300
    n_rows = render_me.height
    if render_me.height > max_rows:
        render_me = render_me.head(max_rows)

    # Rename the 'Fiscal yrtr' column to 'year_term' for clarity
    render_me = render_me.rename({'Fiscal yrtr': 'year_term'})
    
    # Convert all the columns with money values to strings with
    # dollar signs and commas for thousands.
    money_cols = [ 'Tuition Resident', 'Tuition Non-Resident',
                  'Approximate Course Fees', 'Book Cost',]
    render_me = render_me.with_columns([
        pl.col(col)
        .map_elements(lambda x: f"${x:,.2f}" if x is not None else None, return_dtype=pl.Utf8)
        .alias(col)
        for col in money_cols
    ])

    # Convert the 'Last Updated' column to a string representation
    render_me = render_me.with_columns(
        pl.col('Last Updated').dt.strftime('%Y-%m-%d %H:%M:%S').alias('Last Updated')
    )

    # Convert the ID # column to HTML links to the course detail
    # page, using the COURSE_DETAIL_URL defined in config.py.
    COURSE_DETAIL_URL = 'https://eservices.minnstate.edu/registration/search/detail.html?campusid=072&courseid={course_id}&yrtr={year_term}&rcid=0072&localrcid=0072&partnered=false&parent=search'
    fmt_string = "<a href='" + COURSE_DETAIL_URL + "'>{course_id}</a>"
    cleaned_fmt_string = re.sub(r"\{[^}]*\}", "{}", fmt_string)

    # Create a formatted string version of the course ID
    render_me_alt = render_me.with_columns([
        pl.col("ID #").cast(pl.Int64).map_elements(lambda x: f"{x:06}",
                                                   return_dtype=pl.String).alias("course_id_str")
        ])

    render_me_alt = render_me_alt.with_columns(
        pl.format(cleaned_fmt_string,
                  pl.col('course_id_str'),
                  pl.col('year_term'),
                  pl.col('course_id_str')
        ).alias("ID #")
    )

    # Remove the 'course_id_str' column as it is no longer needed
    render_me_alt = render_me_alt.drop('course_id_str')

    # Render table using GreatTables
    rendered_html = (GT(render_me_alt).tab_header(title=subj_text)
                     .cols_hide(columns="year_term")
                     .tab_style( style=style.text(size="14px"), locations=loc.body())
                     .tab_style( style=style.text(size="14px", weight="bold"), locations=loc.column_labels())
                     .opt_row_striping()
                     .as_raw_html()
    )

    # Render the page using the 'results.html' template,
    return render_template('results.html',
                           rendered_table=rendered_html,
                           subject=subj_text,
                           n_rows=n_rows,
                           max_rows=max_rows,
                           oldest=oldest,
                           most_recent=most_recent,
                           sch=stu_credit_hours,
                           csv_file=csv_filename,
                           excel_file=excel_filename,
                           seats=seats,
                           revenue=calulcated_tuition,
                           base_detail_url=COURSE_DETAIL_URL)



# Kept for future enhancements
def filter_data_advanced(tbl, **filters):
    """
    Advanced filtering function that accepts multiple filter parameters for form-based filtering.

    Parameters
    ----------
    tbl : polars Lazy DataFrame
        The table containing course data to be filtered.
    **filters : dict
        Filter parameters that can include:
            - college: str (college code like 'CBAC', 'COAH', etc.)
            - subject: str (subject like 'CSCI', 'MATH', etc.)
            - course_number: str (course number like '241', '101', etc.)
            - term: str (year/term code like '20231', '20235', etc.)
            - lasc_area: str (LASC area like '1A', '2B', etc.)
            - online_only: bool (filter for online courses only)
            - wi_only: bool (filter for WI courses only)
            - all_courses: bool (if True, ignore other filters and return all courses)

    Returns
    -------
    polars Lazy DataFrame
        A Polars LazyFrame with the applied filters.
    str
        A string representation of the filters applied.
    """
    filtered_table = tbl
    filter_descriptions = []

    # Handle 'all_courses' special case
    if filters.get('all_courses'):
        filtered_table = filtered_table
        filter_descriptions.append("All Courses")
    else:
        # Apply college filter
        if filters.get('college'):
            college = filters['college'].upper()
            filtered_table = filtered_table.filter(pl.col('College') == college)
            filter_descriptions.append(f"College: {college}")
        # Apply subject filter
        if filters.get('subject'):
            subject = filters['subject'].upper()
            filtered_table = filtered_table.filter(pl.col('Subj') == subject)
            filter_descriptions.append(f"Subject: {subject}")
        # Apply course number filter
        if filters.get('course_number'):
            course_num = filters['course_number']
            filtered_table = filtered_table.filter(pl.col('#') == course_num)
            filter_descriptions.append(f"Course: {course_num}")
        # Apply term filter
        if filters.get('term'):
            term = int(filters['term'])
            filtered_table = filtered_table.filter(pl.col('Fiscal yrtr') == term)
            # filter_descriptions.append(f"Term: {term}")
        # Apply LASC area filter
        if filters.get('lasc_area'):
            lasc_area = filters['lasc_area'].upper()
            filtered_table = filtered_table.filter(pl.col('LASC/WI').str.contains(lasc_area))
            filter_descriptions.append(f"LASC Area: {lasc_area}")
        # Apply online courses filter
        if filters.get('online_only'):
            filtered_table = filtered_table.filter(pl.col('18online') == True)
            filter_descriptions.append("Online Courses Only")
        # Apply WI courses filter
        if filters.get('wi_only'):
            filtered_table = filtered_table.filter(pl.col('LASC/WI').str.contains('WI'))
            filter_descriptions.append("WI Courses Only")

    subj_text = " | ".join(filter_descriptions) if filter_descriptions else "All Courses"
    filtered_table = filtered_table.sort(
        by=['Fiscal yrtr', 'Subj', '#', 'Sec'],
        descending=[False, False, False, False]
    )
    return filtered_table, subj_text


def sanitize_excel_sheetname(name):
    """
    Sanitize a string to be a valid Excel sheet name (max 31 chars, no invalid chars).
    """
    invalid = r'[:\\/?*\[\]]'
    name = re.sub(invalid, '', name)
    return name[:31]

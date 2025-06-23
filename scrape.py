# This version of scrape was originally written by Matt Craig, but used
# astropy to handle datatables instead of polars.  It also used
# os for functions available via Path, which is now used.
#
# This code was updated by Juan Cabanela in Summer 2025 to use
# polars instead of astropy, and to use Path for file
# handling instead of os.  It has to produce the same output format as
# the old scrape.py, which is why it still uses the same
# column names and structure.

import re
import time
import datetime
import argparse
from pathlib import Path
from collections import defaultdict

import requests
from bs4 import BeautifulSoup
import lxml.html
import numpy as np

import polars as pl

# The URLs below have a few parameters that need to be substituted to
# make them useful. Those parameters are:
#
#   year_term -- see argument definition at end of this file campus_id
#   -- see argument definition at end of this file subject -- see
#   argument definition at end of this file course_id -- Course ID
#   number
#
# Not all URLS use all of these parameters, but putting them all into a
# dict makes it easy to pass around and to .format the strings.
#
URL_COMMON_ROOT = 'https://eservices.minnstate.edu/registration/search/'
URL_ROOT = URL_COMMON_ROOT + 'basic.html?campusid={campus_id:03}'
SUBJECT_SEARCH_URL = URL_COMMON_ROOT + 'advancedSubmit.html?campusid={campus_id:03}&searchrcid={campus_id:04}&searchcampusid={campus_id:03}&yrtr={year_term}&subject={subject}&courseNumber=&courseId=&openValue=ALL&showAdvanced=&delivery=ALL&starttime=&endtime=&mntransfer=&gened=&credittype=ALL&credits=&instructor=&keyword=&begindate=&site=&resultNumber=250'
COURSE_DETAIL_URL = URL_COMMON_ROOT + 'detail.html?campusid={campus_id:03}&courseid={course_id}&yrtr={year_term}&rcid={campus_id:04}&localrcid={campus_id:04}&partnered=false&parent=search'

# The last size key includes a colon because there was a faculty member
# at MSUM whose list name was "Sizer" and "Size" without the colon
# matches that. The first key contains a colon because there was other
# text in one course that contained the word "Enrolled"
SIZE_KEYS = ['Enrolled:', 'Size:']

# Define the directory where the data will be stored.
DATA_DIR = Path('data')
# Confirm that the data directory exists, and create it if it does not.
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Provide stub for the destination directory name within the data directory.
# This will be filled in with a timestamp later.
DESTINATION_DIR_BASE = str( DATA_DIR / 'results_v2' )

# # Name of symlink to create to most recent scrape
# LATEST = str( DATA_DIR / 'latest' )

TUITION_COURSE_KEYS = [
    'Tuition -resident',
    'Tuition -nonresident',
    'Approximate Course Fees'
]

TUITION_PER_CREDIT_KEYS = [
    'Tuition per credit -resident',
    'Tuition per credit -nonresident',
    'Approximate Course Fees'
]

LASC_AREAS = [
    '10-People and the Environment',
    '11-Information Literacy',
    '1A-Oral Communication',
    '1B-Written Communication',
    '2-Critical Thinking',
    '3-Natural Sciences',
    '3L-Natural Sciences with Lab',
    '4-Math/Logical Reasoning',
    '5-History and the Social Sciences',
    '6-Humanities and Fine Arts',
    '7-Human Diversity',
    '8-Global Perspective',
    '9-Ethical and Civic Responsibility',
    'WI-Writing Intensive',
]

# Define some constants for column names...
LASC_WI = 'LASC/WI'
ONLINE_18 = '18online'
TUITION_UNIT = 'Tuition unit'
COURSE_LEVEL = 'Course level'
EXTRA_COLUMNS = [
    LASC_WI,
    ONLINE_18,
    TUITION_COURSE_KEYS[0],  # Resident tuition
    TUITION_UNIT,
    TUITION_COURSE_KEYS[1],  # Course fees
    COURSE_LEVEL,
    TUITION_COURSE_KEYS[2],  # Non-resident tuition
]

DESIRED_ORDER = [
    "ID #","Subj","#","Sec","Title","Dates","Days","Time","Size:","Enrolled:","Cr/Hr",
    "Status","Instructor","Delivery Method","Book Cost","Loc","LASC/WI","18online",
    "Tuition -resident","Tuition unit","Tuition -nonresident","Course level",
    "Approximate Course Fees","timestamp","year_term"
]


def lasc_area_label(full_name):
    """
    Return just the area number/letter from the full name that appears
    in the course detail page.
    """
    return full_name.split('-')[0]


def get_subject_list(params):
    """
    Scrape the list of subjects (aka course rubrics, e.g. PHYS or BCBT)
    for the given year/term.

    Parameters
    ----------

    year_term: str or int
        The year and term for which the list is desired. This should
        follow the "fiscal year" format, in which YYYY3 is the fall of
        fiscal year YYYY, YYYY5 is the spring of fiscal year YYYY and
        summer is...well, summer is something. No idea what. Found out!
        Summer is YYYY1.

    Returns
    -------
    list
        List of course rubrics as strings.
    """
    # print(URL_ROOT.format(**params))
    result = requests.get(URL_ROOT.format(**params))
    soup = BeautifulSoup(result.text, "lxml")
    select_box = soup.find('select', id='subject')
    subjects = select_box.find_all('option', class_=params['year_term'])
    subject_str = [s['value'] for s in subjects]
    return subject_str


def decrap_item(item):
    """
    Utility function to strip out some whitespace. It removes any
    unicode, all line break and tab characters, compresses multiple
    spaces to a single space, and removes any leading/trailing
    whitespace.

    Parameters
    ----------
    item : str
        The raw item scraped from the web page.

    Returns
    -------
    str
        The cleaned up item, with all the whitespace removed.
    """
    remove_nbsp = item.encode('ascii', errors='ignore').decode()
    no_linebreaks = remove_nbsp.replace('\n', '')
    no_linebreaks = no_linebreaks.replace('\r', '')
    no_tabs = no_linebreaks.replace('\t', '')
    less_spaces = re.sub(r'\s+', ' ', no_tabs)
    return less_spaces.strip()


def get_location(loc):
    """
    Extract the class location, which is stored as the alt text in an
    image in one of the table cells.

    Yes, you read that right. Someone thought to themselves 'Hey, you
    know what would be handy? Having to mouse over a little location
    icon and hover to see a list of rooms.'

    It is also available as the title of the image...

    Parameters
    ----------
    loc : lxml.html.HtmlElement
        The table cell containing the location information, which is
        an <img> element with an alt attribute that contains the
        location information.

    Returns
    -------
    str
        A string with the locations of the class, one per line.
    """
    img = loc.find('.//img')
    locations = img.attrib['alt'].splitlines()
    # Drop the first line, which just says the class is at MSUM.
    locations = [l for l in locations if l.startswith('Building')]

    # For the rest, ditch "Building/Room:" from the front of the line
    locations = [l.split('Building/Room: ')[1] for l in locations]
    return '\n'.join(locations)


def scrape_class_data_from_results_table(page_content, page_type='search'):
    """
    Given the html content of either a course search result page or
    an individual course page, scrape the useful data from the table.

    Parameters
    ----------
    page_content : str
        The HTML content of the page to scrape.
    page_type : str, optional
        The type of page to scrape. Either 'search' for a course
        search results page, or 'detail' for an individual course
        detail page. Defaults to 'search'

    Returns
    -------
    polars DataFrame
        A DataFrame with one row for each course, and one column for
        each column in the search results table.
    """
    lxml_parsed = lxml.html.fromstring(page_content)

    # Grab the table of results...
    if page_type == 'search':
        results = lxml_parsed.findall(".//table[@id='resultsTable']")[0]
    else:
        results = lxml_parsed.findall(".//table[@class='myplantable']")[0]

    # ...and then the headers for that table, to use as column names later...
    headers = results.findall('.//th')

    # For reasons I do not understand, the first header, which contains
    # an image, is no longer picked up in headers. It used to be trimmed
    # out here by slicing headers[1:], but that no longer seems
    # necessary. Not happy that I have absolutely no idea why...
    header_list = [decrap_item(h.text_content()) for h in headers]

    # ...and finally grab all of the rows in the table.
    hrows = results.findall('.//tbody/tr')

    # Not clear why data is created and appended to, since it is not
    # actually used for anything.
    data = []

    # Append the data for each row to the table (likely also slow)
    for row in hrows:
        cols = row.findall('td')
        # Skip the first column, which is a set of buttons for user
        # actions, and the last column, which has room information
        # embedded in it, but not as text.
        dat = [decrap_item(c.text_content()) for c in cols[1:-1]]
        # Last column is location
        loc = cols[-1]
        dat.append(get_location(loc))
        data.append(dat)

    # Yay stackoverflow: https://stackoverflow.com/a/6473724/3486425
    data = list(map(list, zip(*data)))

    if not data:
        # So apparently a subject which has no courses can be listed...
        return pl.DataFrame()  # Return an empty DataFrame

    # At this point headers is a list of column names and data is
    # a list of lists, where each inner list is the data for one
    # column. So we can create a table with the headers as column names
    # and the data as the column data.

    # Create a polars DataFrame from the data and headers, all the
    # columns are strings, so we can use pl.Utf8 as the dtype.
    headcounts_df = pl.DataFrame(
        {colname: pl.Series(name=colname, values=coldata, dtype=pl.Utf8)
         for colname, coldata in zip(header_list, data)}
    )
    return headcounts_df


def class_list_for_subject(params):
    """
    Return a table with one row for each class offered in a subject (aka
    course rubric).

    Parameters
    ----------
    params : dict
        Dictionary of parameters for substitution in URLs.

    subject : str
        The course rubric (aka subject) for which the list of courses is
        desired. Examples are PHYS, ED, ART...

    year_term: str, optional
        The year/term in "fiscal year" notation. See the documentation
        for ``get_subject_list`` for a description of that notation.

    Returns
    -------
    Polars DataFrame
        A DataFrame with one column for each column in the search
        results in which each row is one course.
    """

    # Get and parse the course list for this subject
    list_url = SUBJECT_SEARCH_URL.format(**params)
    result = requests.get(list_url)

    # Convert the result text to a DataFrame
    return scrape_class_data_from_results_table(result.text)


def class_list_for_cid(params):
    """
    Return a table with one row for each class offered in a subject (aka
    course rubric).

    This gets that information in a sort of dumb way by scraping it from
    the course detail page.

    Parameters
    ----------
    params : dict
        Dictionary of parameters for substitution in URLs. This must
        include the keys 'campus_id', 'course_id', and 'year_term'.

    Returns
    -------
    Polars DataFrame
        A DataFrame with one column for each column in the search
        results in which each row is one course.
    """

    course_url = COURSE_DETAIL_URL.format(**params)
    result = requests.get(course_url)

    # Convert the result text to a DataFrame
    return scrape_class_data_from_results_table(result.text,
                                                page_type='detail')


def course_detail(params):
    """
    Parse enrollment size information from detail page for a course.

    Note that a failed search for a course gives a result whose values are
    -1, but no exception is raised.

    Parameters
    ----------
    cid : str
        Course ID number, with leading zeros to pad it to six digits.

    Returns
    -------
    dict
        A dict whose keys are the sizes in SIZE_KEYS and whose values are
        either the enrollment number, if the course lookup is successful,
        or **-1 if the course lookup fails**.
    """

    def parse_size_cap(element):
        """
        Handle extracting the actual size from the matched element in the XML
        tree.
        """
        return element.getparent().text_content().split(':')[1].strip()

    # Get and parse the course detail page.
    course_url = COURSE_DETAIL_URL.format(**params)
    result = requests.get(course_url)
    lxml_parsed = lxml.html.fromstring(result.text)

    # Check for an error in the page text, and return sizes of -1 to indicate
    # error.
    if 'System Error' in result.text:
        print("Errored on {}".format(params['course_id']))
        print("URL: ", course_url)
        return {k: -1 for k in SIZE_KEYS}

    if TUITION_PER_CREDIT_KEYS[0] in result.text:
        tuition_keys = TUITION_PER_CREDIT_KEYS
        tuition_unit = 'credit'
    else:
        # if TUITION_COURSE_KEYS[0] in result.text:
        tuition_keys = TUITION_COURSE_KEYS
        tuition_unit = 'course'

    lasc_areas = [lasc_area_label(area) for area in LASC_AREAS
                  if area in result.text]

    # Define an xpath expression to the class sizes. The value $key
    # will be filled in below with one of the SIZE_KEYS.
    xpath_expr = './/*[contains(text(), $key)]'
    to_get = {}

    for key in SIZE_KEYS + tuition_keys:
        foo = lxml_parsed.xpath(xpath_expr, key=key)
        try:
            value = parse_size_cap(foo[0])
        except IndexError:
            value = ''
        # Make the sizes integers
        if key in SIZE_KEYS:
            value = int(value)

        # If we have one of the per-credit keys change it to a per-course key
        try:
            idx = TUITION_PER_CREDIT_KEYS.index(key)
        except ValueError:
            to_get[key] = value
        else:
            use_key = TUITION_COURSE_KEYS[idx]
            to_get[use_key] = value

    # Add a couple last things to the results...
    to_get[TUITION_UNIT] = tuition_unit
    to_get[LASC_WI] = ','.join(lasc_areas)
    to_get[ONLINE_18] = '18 On-Line' in result.text

    # So....how do you get free floating text in a web page out of that page?
    # Any suggestions, MnSCU? Didn't think so. How about a regex for what
    # we need, which is sandwiched between two divs that contain text that is
    # easy to find? Note the actual text is not in any element, not even a <p>.
    all_the_text = lxml_parsed.text_content()
    matches = re.search(r'.*Course Level\s+(\w+)\s+(Description|General/Liberal|Lectures/Labs|Corequisites|Add To Wait List|Minnesota Transfer Curriculum Goal|Non-Course Prerequisites)',
                        all_the_text)

    # Oh ha, ha, turns out any number of things can follow Course Level.
    if matches:
        to_get[COURSE_LEVEL] = matches.groups(1)[0]
    else:
        to_get[COURSE_LEVEL] = 'Unknown'
        raise RuntimeError('Failed to find "Course Level" '
                           'in URL {}'.format(course_url))

    return to_get


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape enrollment numbers '
                                     'from public MnSCU search site')
    parser.add_argument('--year-term', action='store',
                        help='Code for year/term, a 5 digit '
                        'number like 20155 (spring of 2015)')
    parser.add_argument('--cid-list', action='store',
                        help='CSV that has at least two columns, "ID #", a '
                        'course ID number, and "year_term" a year/term code.')
    parser.add_argument('--campus-id', action='store', type=int,
                        default='72',
                        help='Two digit code number for the campus data '
                        'should be gathered for.')
    args = parser.parse_args()

    year_term = args.year_term
    cid_list = args.cid_list

    if year_term and cid_list:
        raise RuntimeError('Can only use one of '
                           '--year-term and --cid-list')
    elif not (year_term or cid_list):
        raise RuntimeError('Must use exactly one of '
                           '--year-term and --cid-list')

    # print(year_term)

    # Define dict used for passing parameters. Values will mostly be
    # filled in later. Make sure campus_id is an integer because we
    # need to do some integer formatting on it.
    url_params = dict(year_term=None, subject=None,
                      course_id=None, campus_id=args.campus_id)

    if year_term:
        url_params['year_term'] = args.year_term
        # Grab the list of subjects for this year/term
        subjects = get_subject_list(url_params)
        source_list = subjects

    if cid_list:
        inp_data = pl.read_csv(cid_list)
        cids = inp_data['ID #'].to_list()
        year_terms = inp_data['year_term'].to_list()
        source_list = [('{:06d}'.format(int(c)), str(y)) for
                       c, y in zip(cids, year_terms)]

    # Quit if there is no data to scrape.
    if len(source_list) == 0:
        raise RuntimeError(f'No data found for {url_params}')

    # Make backup copy of muteable url_params dict
    original_url_params = url_params.copy()

    # print "Trying {}".format(subjects[0])

    # Define composite dataframe to hold all of the data across all
    # courses as an empty polars DataFrame.
    composite_df = pl.DataFrame()

    # Generate a date/time to use in naming directory with results
    now = time.localtime()
    formatted_datetime = datetime.datetime(*now[:-3]).isoformat()
    formatted_datetime = formatted_datetime.replace(':', '-')
    destination = '-'.join([DESTINATION_DIR_BASE, formatted_datetime])
    if args.campus_id != 72:
        # Sorry other campuses, you get separate folders.
        p = Path(str(args.campus_id)) / destination
        destination = str(p)

    # Make the directory
    try:
        Path(destination).mkdir(parents=True, exist_ok=False)
    except OSError:
        raise OSError('Destination folder %s already exists' % destination)

    temp_paths = []
    bads = []

    # Process each course rubric (aka subject)
    print(f"Processing {len(source_list)} subjects...")
    for source in source_list:
        # Notify user of progress
        print(f"{source}", end="", flush=True)

        # Pull list of classes for subject. Note that this is dataframe
        # from which most of the course information is derived.
        try:
            if year_term:
                url_params['year_term'] = year_term
                url_params['subject'] = source
                data_df = class_list_for_subject(url_params)
            elif cid_list:
                url_params['year_term'] = source[1]
                url_params['course_id'] = source[0]
                data_df = class_list_for_cid(url_params)

            # Check for an empty DataFrame, which can happen if there are
            # no courses listed for a subject.
            if data_df.is_empty():
                # This can happen, for example, if there are no courses listed
                # for a subject...
                bads.append(source)
                print(" (No courses) .. ", end="", flush=True)
                continue
        except IndexError:
            bads.append(source)
            print(" (Failed)", end="", flush=True)
            continue

        # Get the IDs of the courses from the DataFrame.
        IDs = data_df['ID #']

        # Create a mew results dictionary to hold data (it defaults
        # to empty lists for each key).
        results = defaultdict(list)
        timestamps = []

        use_year_term = year_term or source[1]
        url_params['year_term'] = use_year_term

        # Obtain the enrollment and enrollment cap, and add a timestamp.
        original_course_id = url_params['course_id']
        for an_id in IDs:
            url_params['course_id'] = an_id
            size_info = course_detail(url_params)
            for k, v in size_info.items():
                results[k].append(v)
            timestamps.append(time.time())

        # Reset the url_params to the original values, so that
        # we can use it again for the next subject.
        url_params['course_id'] = original_course_id

        # Add columns from course detail to the polars dataframe
        for k in SIZE_KEYS:
            data_df = data_df.with_columns(
                pl.Series(name=k, values=results[k], dtype=pl.Int64)
            )

        # Because polars casts booleans to strings as lowercase, to match
        # the old astropy code, we need to convert the boolean values
        # to strings.
        for k in EXTRA_COLUMNS:
            col_values = results[k]
            # If the first value in column is boolean, typecast using
            # str() convert booleans to capitalized string
            if isinstance(col_values[0], bool):
                col_values = [str(v) for v in col_values]
            # Add the column to the DataFrame
            data_df = data_df.with_columns(
                pl.Series(name=k, values=col_values, dtype=pl.Utf8)
            )

        # Add a timestamp column to the table
        data_df = data_df.with_columns(
            pl.Series(name='timestamp', values=timestamps, dtype=pl.Float64)
        )

        # Add a year_term column to the table
        data_df = data_df.with_columns(
            pl.Series(name='year_term', values=[str(use_year_term)] * len(data_df),
                      dtype=pl.Utf8)
        )

        # Reorder columns to be in the desired order.
        data_df = data_df.select(DESIRED_ORDER)

        # Replace all empty strings with None, so that they are
        # properly recognized as missing values in polars.
        data_df = data_df.with_columns([
            pl.when(pl.col(col).cast(pl.Utf8) == '').then(None).otherwise(pl.col(col)).alias(col)
            for col in data_df.columns if data_df.schema[col] == pl.Utf8
        ])

        # Add the table to the overall table...
        if composite_df.is_empty():
            composite_df = data_df
        else:
            composite_df = pl.concat([composite_df, data_df])

        # ...but also write out this individual table in case we have a
        # failure along the way.
        temp_file = source + '.csv'
        temp_path = Path(destination) / temp_file
        data_df.write_csv(temp_path)
        temp_paths.append(temp_path)

        print(f" .. ", end="", flush=True)

    print(" Done.")
    print(f"Processed {len(source_list) - len(bads)} subjects, "
          f"failed on {len(bads)} subjects. A total of {len(composite_df)} "
          "courses were processed.")
    
    # Write out a file for the overall (i.e. all subjects) table.
    output_file = Path(destination) /  'all_enrollments.csv'
    composite_df.write_csv(output_file)

    # Verify that the table wrote out correctly
    from_disk = pl.read_csv(output_file)

    if len(from_disk) != len(composite_df):
        raise RuntimeError('Enrollment data did not properly write to disk!')

    for path in temp_paths:
        Path(path).unlink()

    # Print the directory where the results were saved.
    print(f"Results saved to: {str(output_file)}")

    # # symlink LATEST to this run of the scraper.
    # latest_path = Path(LATEST)
    # try:
    #     latest_path.unlink()
    # except FileNotFoundError:
    #     pass
    # latest_path.symlink_to(destination)

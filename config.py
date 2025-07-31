# Define the base URL for course detail pages
# The placeholders in the URL will be replaced with actual course data
COURSE_DETAIL_URL = 'https://eservices.minnstate.edu/registration/search/detail.html?campusid=072&courseid={course_id}&yrtr={year_term}&rcid=0072&localrcid=0072&partnered=false&parent=search'

# Define the source URL for the course data
COURSE_DATA_SOURCE_URL = 'https://eservices.minnstate.edu/registration/search/basic.html?campusid=072'

# Define the directory where cached CSV files will be stored for 
# possible download
CACHE_DIR = 'viewed-csvs'

# Define the data file to use
PARQUET_DATA = 'all_enrollments.parquet'

##
## These constants are used to set up the data import process
## in update_data_table.py
##

# Define path to CSV file for export (must be same as PARQUET_DATA but with
# .csv extension)
CSV_DATA = 'all_enrollments.csv'

# Define the directory where the scraped data will be stored.
SCRAPE_DIR = 'data/'

# Define the directory where setup files are stored defining colleges at 
# MSUM
SETUP_DIR = 'assets/'

# Define the directory where backup files are stored
BACKUP_DIR = 'backups/'

# Python file to import for list of semesters
SEMESTER_PY = 'config_terms.py'

# Default term for the application
DEFAULT_TERM = (20263, 'Fall 2025')
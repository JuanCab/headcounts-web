# Define the base URL for course detail pages
# The placeholders in the URL will be replaced with actual course data
COURSE_DETAIL_URL = 'https://eservices.minnstate.edu/registration/search/detail.html?campusid=072&courseid={course_id}&yrtr={year_term}&rcid=0072&localrcid=0072&partnered=false&parent=search'

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

# Define the directory where setup files are stored defining colleges at 
# MSUM
SETUP_DIR = 'msum_setup/'

# Define the directory where backup files are stored
BACKUP_DIR = 'backups/'
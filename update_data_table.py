# This code is used to merge new enrollment data into an existing
# dataset, updating existing entries and appending new ones as needed
#
# The initial version of this was developed by Matt Craig and used the
# astropy Table data structure to hold the table.
#
# In Summer 2025, Juan Cabanela developed a new version of this code
# with the following changes:
# - The documentation was updated to reflect the changes in the code and
#   to be a little more complete.
# - It uses the Polars library to handle the data, which allows for
#   quicker handling of the data and more efficient memory usage.
# - The cumulative enrollment data is now always backed up before
#   updating, so that the previous version is always available.
# - In addition to exporting data in CSV format, the code now also
#   exports the data in Parquet format, which is more efficient for
#   storage (as it is compressed) and analytical processing (as it is
#   columnar) and also allows me to add some addition columns including:
#   - Rename some columns to be a little clearer titles.
#   - Precomputing the "term name" and adding that as a column.
#   - Adding the college a particular rubric is associated with.
#
# November 19, 2025: Updated to fix an issue with courses that are
#  no longer offered or in the course catalog somehow showing up, they
#  were there at some pointbut now are not.  So when we update the
#  data for a given semester, we first need to actually remove any
#  entries for that semester from the current data before adding
#  the new data for that semester.

import polars as pl
from datetime import datetime
from config import CSV_DATA, PARQUET_DATA, BACKUP_DIR, SEMESTER_PY, RUBRIC_TO_COLLEGE


def add_index_col(df):
    """
    Given a dataframe, construct an index column that is unique for
    each row. The index is a concatenation of the year_term, ID #,
    Subj, and # columns.

    Parameters
    ----------
    df : polars.DataFrame
        The dataframe to which the index column will be added.

    Returns
    -------
    df : polars.DataFrame
        The dataframe with the index column added.
    """

    # Add index column to the dataframe and return it
    return df.with_columns(
        (pl.col('year_term').cast(str) +
         pl.col('ID #').cast(str) +
         pl.col('Subj').cast(str) +
         pl.col('#').cast(str)).alias('index')
    )


def main(new_data_file):
    # Load the original data
    current_df = pl.read_csv(CSV_DATA)
    print(f"Loaded {len(current_df)} entries of current data.")

    # Create a backup of the current data using the date and time
    # to create a unique filename.
    backup_file = f"{BACKUP_DIR}all_enrollments_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    current_df.write_csv(backup_file)
    print(f"Backup created: {backup_file}")

    # Load the new data from new_data_file
    new_df = pl.read_csv(new_data_file)

    # Rename columns to match the current data format
    new_df = new_df.rename({'Enrolled:': 'Enrolled', 'Cr/Hr': 'Crds'})

    # Determine the current semester from the new data
    if 'year_term' not in new_df.columns:
        raise ValueError(
            "The new data file must contain a 'year_term' column.")
    current_semester = new_df.select(
        pl.col('year_term')).unique().to_series()[0]
    print(
        f"Semester for new data identified as year_term = {current_semester}.")

    # Add an index column to both dataframes
    new_df = add_index_col(new_df)
    current_df = add_index_col(current_df)

    # Previously I would identify all the rows in the existing
    # data file that need to be removed and replaced with the new
    # data. Now instead we will just remove all entries for the
    # current semester from the existing data, and then add all
    # of the new data for that semester.

    # Count how many entries are being removed
    num_before = len(current_df)
    current_rows_to_keep = current_df.filter(
        pl.col('year_term') != current_semester
    )
    num_after = len(current_rows_to_keep)
    num_removed = num_before - num_after
    print(
        f"Removing {num_removed} entries from current data for year_term = {current_semester}.")

    # Combine the rows that need to be kept with the updated rows
    result_df = pl.concat([current_rows_to_keep, new_df])
    num_final = len(result_df)
    num_added = num_final - num_after
    print(f"Added {num_added} new entries for year_term = {current_semester}.")
    print(
        f"Current data now has {num_final} entries after removing old semester data and adding new data.")

    # Remove the (now unnecessary) index column from the result_df
    result_df = result_df.drop('index')

    # Check for missing tuition values in the new data and set it to
    # zero if it is an integer type.
    last_cols = ['Tuition -resident',
                 'Tuition -nonresident',
                 'Approximate Course Fees',
                 'Book Cost']
    for tuition in last_cols:
        # Check for null values in the tuition column and replace with
        # $0.00
        result_df = result_df.with_columns(
            pl.when(pl.col(tuition).is_null())
            .then(pl.lit("$0.00"))
            .otherwise(pl.col(tuition))
            .alias(tuition)
        )
        # Check for all "n/a" values in the tuition column and replace with
        # $0.00
        result_df = result_df.with_columns(
            pl.when(pl.col(tuition).str.to_lowercase() == 'n/a')
            .then(pl.lit("$0.00"))
            .otherwise(pl.col(tuition))
            .alias(tuition)
        )

    # Fix weird glitch where "zz" is inserted into the location.
    # We remove ALL instances of "zz" in the location column.
    result_df = result_df.with_columns(
        pl.col('Loc').str.replace_all(r'zz', '').alias('Loc')
    )

    # # Sort the data year_term descending, then by Subj, #, Sec
    # result_df = result_df.sort(
    #     by=['year_term', 'Subj', '#', 'Sec'],
    #     descending=[False, False, False, False]
    # )

    # Save the updated dataframe to the CSV file
    result_df.write_csv(CSV_DATA)

    #
    # PARQUET FILE PROCESSING
    #
    # Now make changes to columns to make data more useful and store the
    # updated dataframe in a Parquet file.
    #

    # Convert all null values for 'Delivery Method' to 'On Campus'
    result_df = result_df.with_columns(
        pl.when(pl.col('Delivery Method').is_null())
        .then(pl.lit("On Campus"))
        .otherwise(pl.col('Delivery Method'))
        .alias('Delivery Method')
    )

    # Convert all the tuition columns from dollar strings to floats
    for col in last_cols:
        if col in result_df.columns:
            result_df = result_df.with_columns(
                pl.col(col).str.replace_all(r'[$,]', '').cast(float)
            )

    # Convert 'timestamp' column which is unix timestamp into a datetime
    # in ISO format
    if 'timestamp' in result_df.columns:
        # Convert unix timestamp to datetime (in naive UTC)
        result_df = result_df.with_columns(
            pl.from_epoch(pl.col('timestamp'),
                          time_unit="s").alias('timestamp')
        )
        # Make sure it is in the central time zone
        result_df = result_df.with_columns(
            (pl.col("timestamp").dt.convert_time_zone("America/Chicago")
             .alias("timestamp"))
        )

    # Add a column for the year_term in a human-readable format, make it
    # the first column in the dataframe. This involves creating several
    # temporary columns to hold the year and term code, then merging the
    # two into a single column.
    result_df = result_df.with_columns(
        pl.col("year_term").cast(str).str.slice(
            0, 4).cast(pl.Int32).alias("fiscal_year"),
        pl.col("year_term").cast(
            str).str.slice(-1).cast(pl.Int32).alias("term_code")
    )
    # If the term code is 5 (Spring), then the year is the fiscal year
    # otherwise it is the fiscal year - 1
    result_df = result_df.with_columns(
        pl.when(pl.col("term_code") == 5).then(pl.col("fiscal_year"))
        .otherwise(pl.col("fiscal_year") - 1).alias("year")
    )
    # Create a human-readable term name based on the term code
    term_map = {1: "Summer", 3: "Fall", 5: "Spring"}
    result_df = result_df.with_columns(
        pl.col("term_code").replace_strict(
            term_map, default=None).alias("term_name")
    )
    # Finally, create a term name column that combines the term name
    # and year
    result_df = result_df.with_columns(
        pl.concat_str(
            [pl.col("term_name"), pl.col("year").cast(pl.Utf8)],
            separator=" "
        ).alias("Term")
    )
    # Drop all the temporary columns we created
    result_df = result_df.drop(
        ["fiscal_year", "term_code", "year", "term_name"])

    # Set the order of the first few columns to be a fixed order
    first_cols = ['Term', 'year_term', 'ID #', 'Subj', '#', 'Sec', 'Title',
                  'Crds', 'Enrolled', 'Size:', 'Status']
    result_df = result_df.select(
        *first_cols,
        *[col for col in result_df.columns if col not in first_cols]
    )

    # Map the "Subj" column to a college code using the RUBRIC_TO_COLLEGE
    # dict defined in config.py. Unknown rubrics default to 'NONE'.
    result_df = result_df.with_columns(
        pl.col('Subj').replace(RUBRIC_TO_COLLEGE,
                               default='NONE').alias('College')
    )

    # Make sure the following columns are the last few columns in the
    # dataframe in this order
    last_cols = ['College', 'Tuition unit', 'Tuition -resident', 'Tuition -nonresident',
                 'Approximate Course Fees', 'Book Cost', 'timestamp']
    result_df = result_df.select(
        *[col for col in result_df.columns if col not in last_cols],
        *last_cols
    )

    # Rename some columns
    rename_map = {
        'Size:': 'Size',
        'Crds': 'Credits',
        'Tuition -resident': 'Tuition Resident',
        'Tuition -nonresident': 'Tuition Non-Resident',
        'year_term': 'Fiscal yrtr',
        'timestamp': 'Last Updated'
    }
    result_df = result_df.rename(rename_map)

    # Dump the parquet file
    result_df.write_parquet(PARQUET_DATA)
    print(f"Updated data saved to {CSV_DATA} and {PARQUET_DATA}")

    # Dump out a list of tuples consisting lf all the unique year_terms
    # and the corresponding Semester name into a Python file to be
    # imported later.  This is the SEMESTER_PY file which defines the
    # SEMESTERS_LIST variable.
    semesters_list = result_df.select(
        pl.col('Fiscal yrtr').cast(str).alias('year_term'),
        pl.col('Term')
    ).unique().sort('year_term', descending=True).to_dicts()
    print(
        f"Found {len(semesters_list)} unique semesters to write to {SEMESTER_PY}")
    with open(SEMESTER_PY, 'w') as f:
        f.write("SEMESTERS_LIST = [\n")
        # Make the list of tuples, year_term as integer and Term as string
        for semester in semesters_list:
            f.write(f"    ({semester['year_term']}, '{semester['Term']}'),\n")
        f.write("]\n")

    # Return the resulting dataframe
    return result_df


if __name__ == '__main__':
    # Parse command line arguments to get the new data file
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('new_data', help='New data in csv format')
    args = parser.parse_args()

    # Call the main function
    result_df = main(args.new_data)

    # Print some feedback
    print(
        f"Data updated successfully. {len(result_df)} total rows in the dataset.")
    print("The last 5 rows of the updated dataset:")
    print(result_df.tail())
    print("with columns:")
    print(result_df.columns)

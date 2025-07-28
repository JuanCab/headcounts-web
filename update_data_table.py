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

import polars as pl
from datetime import datetime
from config import CSV_DATA, PARQUET_DATA, SETUP_DIR, BACKUP_DIR, SEMESTER_PY


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

    # Add an index column to both dataframes
    new_df = add_index_col(new_df)
    current_df = add_index_col(current_df)

    # Now the trick is to identity all the rows in the existing
    # data file that need to be removed and replaced with the new
    # data.
    #
    # Switch things up a bit, maybe. Do an outer join that includes all
    # of the new data. This will be a lef join of the current data with
    # the new data, which will include all of the new data and the
    # matching rows of the current data set.
    joined_df = new_df.join(current_df,
                             on='index', how='left', suffix='_current')

    # Identify the common entries in the joined dataframe and the
    # unique entries in the new data that we need to append
    common_entries_df = joined_df.filter(
        pl.col('year_term_current').is_not_null()
    )
    data_to_append_df = joined_df.filter(
        pl.col('year_term_current').is_null()
    )

    # Update the current dataframe with the common data
    if not common_entries_df.is_empty():
        # Replace each current_df row with a matching index in the
        # common_entries_df with the matching entries from the common_entries_df
        print(f"Updated {len(common_entries_df)} common entries in the current data.")

        # Get the updated data from the common entries
        updated_rows_df = common_entries_df.select(
            pl.exclude([col for col in common_entries_df.columns
                        if col.endswith('_current')])
        )

        # Convert the 'index' column of updated_rows_df to a Python list
        updated_indices = updated_rows_df['index'].to_list()

        # Select all rows from current_df that are NOT in the
        # updated_rows_df (based on index)
        current_rows_to_keep = current_df.filter(
            ~pl.col('index').is_in(updated_indices)
        )

        # Combine the rows that need to be kept with the updated rows
        current_df = pl.concat([current_rows_to_keep, updated_rows_df])

    # Make the current output dataframe based on the current dataframe
    # assuming it has been updated with the common entries (if any)
    result_df = current_df

    # Now append any new data that is not already in the current
    # dataframe.
    if not data_to_append_df.is_empty():
        print(f"Adding {len(data_to_append_df)} new entries in the current data.")
        # Select the data to append, excluding the current data columns
        new_rows_df = data_to_append_df.select(
            pl.exclude([col for col in data_to_append_df.columns
                        if col.endswith('_current')])
        )

        # Append the new data to the current dataframe
        result_df = pl.concat([result_df, new_rows_df])

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
            pl.from_epoch(pl.col('timestamp'), time_unit="s").alias('timestamp')
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
        pl.col("year_term").cast(str).str.slice(0, 4).cast(pl.Int32).alias("fiscal_year"),
        pl.col("year_term").cast(str).str.slice(-1).cast(pl.Int32).alias("term_code")
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
        pl.col("term_code").replace_strict(term_map,default=None).alias("term_name")
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
    result_df = result_df.drop(["fiscal_year", "term_code", "year", "term_name"])

    # Set the order of the first few columns to be a fixed order
    first_cols = ['Term', 'year_term', 'ID #', 'Subj', '#', 'Sec', 'Title', 
                  'Crds', 'Enrolled', 'Size:', 'Status' ]
    result_df = result_df.select(
        *first_cols,
        *[col for col in result_df.columns if col not in first_cols]
    )

    # Read in the rubric to college mapping file
    rubric2college_df = pl.read_csv(f'{SETUP_DIR}Rubric2College.csv')

    # Map the "Subj" column to the "College" column using the
    # rubric2college_df dataframe
    result_df = result_df.join(
        rubric2college_df,
        left_on='Subj',
        right_on='Rubric',
        how='left'
    )
    result_df = result_df.drop('College').rename({'CollegeCode': 'College'})

    # Make sure the following columns are the last few columns in the
    # dataframe in this order
    last_cols = ['College', 'Tuition unit', 'Tuition -resident', 'Tuition -nonresident',
                    'Approximate Course Fees', 'Book Cost','timestamp']
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
    print(f"Found {len(semesters_list)} unique semesters to write to {SEMESTER_PY}")
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
    print(f"Data updated successfully. {len(result_df)} total rows in the dataset.")
    print("The last 5 rows of the updated dataset:")
    print(result_df.tail())
    print("with columns:")
    print(result_df.columns)

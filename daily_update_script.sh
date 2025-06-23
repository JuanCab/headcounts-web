#!/bin/bash

# Activate the Conda environment
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate headspace
#echo "Conda env: $CONDA_DEFAULT_ENV"

# Define a Bash array with the arguments
year_terms=("20261" "20263")  # Replace with your desired arguments

# Loop through the array and call the Python script for each argument
for year_term in "${year_terms[@]}"; do
    echo "Processing data for term: $year_term"
    # Capture the output of the scrape.py script
    output=$(python ./scrape.py --year-term "$year_term")
    echo $output

    # Extract the file path from the line "Results saved to: <file path>"
    file_path=$(echo "$output" | awk -F'Results saved to: ' '/Results saved to:/ {print $2}')
    echo "File path extracted: $file_path"
    
    # Check if a file path was found
    if [[ -n "$file_path" ]]; then
        # Use the file path as an argument for another Python script
        python ./update_data_table.py "$file_path"
    else
        echo "No file path found in the output for year-term: $year_term"
    fi
done
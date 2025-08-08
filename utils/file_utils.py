# utils/file_utils.py

# Import standard Python libraries for interacting with the operating system and handling JSON data.
import os
import json

def check_existing_files(root_dir):
    """
    Scans a directory recursively and returns a set of all PDF filenames found.
    NOTE: This function is not currently used by the agent but is a useful utility for other potential tasks.
    
    Args:
        root_dir (str): The root directory to start scanning from.
        
    Returns:
        set: A set of filenames (e.g., {"report_a.pdf", "report_b.pdf"}).
    """
    # A 'set' is used to efficiently store filenames and prevent duplicates.
    existing_files = set()
    # Check if the directory exists before trying to scan it.
    if not os.path.exists(root_dir):
        print(f"Base directory '{root_dir}' not found. It will be created when a file is saved.")
        return existing_files
    
    # os.walk() efficiently navigates through a directory tree (all folders and subfolders).
    for dirpath, _, filenames in os.walk(root_dir):
        # Loop through all filenames found in the current directory.
        for f in filenames:
            # Check if the file is a PDF.
            if f.endswith('.pdf'):
                # Add the filename to our set.
                existing_files.add(f)
                
    print(f"Found {len(existing_files)} existing PDF reports in '{root_dir}'.")
    return existing_files

def load_download_log(log_path):
    """Loads the success log file ('download_log.json') and returns a set of all URLs found within it."""
    # If the log file doesn't exist, return an empty set to avoid errors.
    if not os.path.exists(log_path):
        return set()
    # Open the file in read mode ('r'). 'with open' ensures the file is automatically closed.
    with open(log_path, 'r') as f:
        # Load the JSON content into a Python dictionary.
        data = json.load(f)
        # We only need the dictionary keys (the URLs) to check if a report has been downloaded.
        # Returning a 'set' makes checking for existence very fast.
        return set(data.keys())

def update_download_log(log_path, url, final_filename):
    """Updates the success log file with a new URL and its corresponding filename."""
    data = {}
    # If the log file already exists, read its contents first.
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            try:
                # Load the existing JSON data.
                data = json.load(f)
            except json.JSONDecodeError:
                # If the file is empty or corrupted, start with an empty dictionary.
                pass
    
    # Add the new report's URL and filename as a new key-value pair.
    data[url] = final_filename
    
    # Open the file in write mode ('w'), which overwrites the old file.
    with open(log_path, 'w') as f:
        # Write the updated dictionary back to the file in a clean, human-readable format.
        json.dump(data, f, indent=4)

def load_failed_log(log_path):
    """Loads the failed log file and returns its contents as a dictionary of {url: reason}."""
    if not os.path.exists(log_path):
        return {}
    with open(log_path, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # If the file is empty or corrupted, return an empty dictionary.
            return {}

def update_failed_log(log_path, url, reason):
    """Updates the failed log with a new URL and the reason for its failure."""
    # First, load all existing data from the failed log.
    data = load_failed_log(log_path)
    # Add or update the entry for the given URL. We convert the 'reason' to a string just in case.
    data[url] = str(reason)
    # Write the entire updated dictionary back to the file.
    with open(log_path, 'w') as f:
        json.dump(data, f, indent=4)

def load_irrelevant_log(log_path):
    """Loads the irrelevant log file and returns a set of all URLs found within it."""
    if not os.path.exists(log_path):
        return set()
    with open(log_path, 'r') as f:
        try:
            data = json.load(f)
            # We only need the keys (URLs) to check for existence, so we return a set.
            return set(data.keys())
        except json.JSONDecodeError:
            return set()

def update_irrelevant_log(log_path, url, reason="Marked as irrelevant by user"):
    """Updates the irrelevant log with a new URL."""
    data = {}
    # Load any existing data from the irrelevant log.
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                pass
    # Add or update the entry for the given URL.
    data[url] = reason
    # Write the updated data back to the file.
    with open(log_path, 'w') as f:
        json.dump(data, f, indent=4)
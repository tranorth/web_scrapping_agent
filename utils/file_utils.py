import os
import json

def check_existing_files(root_dir):
    """
    Scans a directory recursively and returns a set of all PDF filenames found.
    
    Args:
        root_dir (str): The root directory to start scanning from.
        
    Returns:
        set: A set of filenames (e.g., {"report_a.pdf", "report_b.pdf"}).
    """
    existing_files = set()
    if not os.path.exists(root_dir):
        print(f"Base directory '{root_dir}' not found. It will be created when a file is saved.")
        return existing_files
    
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith('.pdf'):
                existing_files.add(f)
                
    print(f"Found {len(existing_files)} existing PDF reports in '{root_dir}'.")
    return existing_files

def load_download_log(log_path):
    """Loads the download log file and returns a set of URLs."""
    if not os.path.exists(log_path):
        return set()
    with open(log_path, 'r') as f:
        # We only need the keys (the URLs) for our check
        data = json.load(f)
        return set(data.keys())

def update_download_log(log_path, url, final_filename):
    """Updates the download log with a new URL and filename."""
    data = {}
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                # File is empty or corrupt, start fresh
                pass
    
    data[url] = final_filename
    
    with open(log_path, 'w') as f:
        json.dump(data, f, indent=4)

def load_failed_log(log_path):
    """Loads the failed log file and returns a dictionary of {url: reason}."""
    if not os.path.exists(log_path):
        return {}
    with open(log_path, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def update_failed_log(log_path, url, reason):
    """Updates the failed log with a new URL and failure reason."""
    data = load_failed_log(log_path)
    data[url] = str(reason) # Ensure reason is a string
    with open(log_path, 'w') as f:
        json.dump(data, f, indent=4)

def load_irrelevant_log(log_path):
    """Loads the irrelevant log file and returns a set of URLs."""
    if not os.path.exists(log_path):
        return set()
    with open(log_path, 'r') as f:
        try:
            data = json.load(f)
            return set(data.keys()) # We only need the URLs
        except json.JSONDecodeError:
            return set()

def update_irrelevant_log(log_path, url, reason="Marked as irrelevant by user"):
    """Updates the irrelevant log with a new URL."""
    data = {}
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                pass
    data[url] = reason
    with open(log_path, 'w') as f:
        json.dump(data, f, indent=4)

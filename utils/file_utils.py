import os

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
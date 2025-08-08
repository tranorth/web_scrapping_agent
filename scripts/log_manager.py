# scripts/log_manager.py

import os
import json
import argparse

# --- Robust Path Definition ---
# This section defines the absolute paths to the log files, making the script
# runnable from any directory without breaking.

# Get the directory where this script is located (e.g., .../your_project/scripts).
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to find the project's root directory.
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
# Create a reliable path to the CBRE_Reports folder, which is in the project root.
BASE_REPORT_PATH = os.path.join(PROJECT_ROOT, "CBRE_Reports")

# Define the full paths to each of the three log files.
SUCCESS_LOG_PATH = os.path.join(BASE_REPORT_PATH, "download_log.json")
FAILED_LOG_PATH = os.path.join(BASE_REPORT_PATH, "failed_log.json")
IRRELEVANT_LOG_PATH = os.path.join(BASE_REPORT_PATH, "irrelevant_log.json")

def _load_log(path):
    """
    Safely loads a JSON log file.
    This is a reusable helper function to avoid duplicating code.
    """
    # If the log file doesn't exist yet, return an empty dictionary.
    if not os.path.exists(path):
        return {}
    # Open the file for reading ('r').
    with open(path, 'r') as f:
        try:
            # Try to load the JSON content into a Python dictionary.
            return json.load(f)
        except json.JSONDecodeError:
            # If the file is empty or corrupted, return an empty dictionary to prevent errors.
            return {}

def promote_to_success(url_to_promote: str, new_filename: str):
    """Moves a URL from the failed log to the success log."""
    # Load the current state of the failed and success logs into memory.
    failed_log = _load_log(FAILED_LOG_PATH)
    success_log = _load_log(SUCCESS_LOG_PATH)

    # Verify that the URL you want to promote actually exists in the failed log.
    if url_to_promote not in failed_log:
        print(f"\n❌ Error: URL not found in the failed log.\n'{url_to_promote}'")
        return

    # Use .pop() to remove the entry from the failed log dictionary.
    reason = failed_log.pop(url_to_promote)
    # Add the new entry to the success log dictionary with the correct filename.
    success_log[url_to_promote] = new_filename

    # Write the modified dictionaries back to their respective files, overwriting them.
    with open(FAILED_LOG_PATH, 'w') as f:
        json.dump(failed_log, f, indent=4)
    with open(SUCCESS_LOG_PATH, 'w') as f:
        json.dump(success_log, f, indent=4)

    print("\n✅ Promotion complete!")
    print(f"✓ Moved '{url_to_promote[:50]}...' to success log.")

def mark_as_irrelevant(url_to_mark: str):
    """Moves a URL from the failed log to the irrelevant log."""
    # Load the current state of the failed and irrelevant logs.
    failed_log = _load_log(FAILED_LOG_PATH)
    irrelevant_log = _load_log(IRRELEVANT_LOG_PATH)

    # Verify that the URL you want to mark as irrelevant exists in the failed log.
    if url_to_mark not in failed_log:
        print(f"\n❌ Error: URL not found in the failed log.\n'{url_to_mark}'")
        return

    # Remove the entry from the failed log.
    reason = failed_log.pop(url_to_mark)
    # Add the entry to the irrelevant log with a standard message.
    irrelevant_log[url_to_mark] = "Marked as irrelevant by user."

    # Write the modified dictionaries back to their respective files.
    with open(FAILED_LOG_PATH, 'w') as f:
        json.dump(failed_log, f, indent=4)
    with open(IRRELEVANT_LOG_PATH, 'w') as f:
        json.dump(irrelevant_log, f, indent=4)

    print("\n✅ Marked as irrelevant!")
    print(f"✓ Moved '{url_to_mark[:50]}...' to irrelevant log.")


# --- HOW TO RUN THIS SCRIPT ---
#
# 1. Open your terminal or command prompt.
# 2. Navigate to your project's root directory.
# 3. Choose one of the two commands below based on your manual review.
#
# ----------------- USAGE EXAMPLES -----------------
#
# To PROMOTE a file you have fixed and renamed:
# python scripts/log_manager.py promote "https://www.cbre.com/insights/figures/jackson-ms-industrial-figures-report-2023" "Jackson MS 2023.pdf"
#
# To MARK a file as IRRELEVANT after reviewing it:
# python scripts/log_manager.py mark-irrelevant "https://www.cbre.com/insights/figures/q1-2025-us-net-lease-investment-figures"
# --------------------------------------------------


# This block ensures the code below only runs when the script is executed
# directly from the command line (e.g., `python log_manager.py ...`).
if __name__ == "__main__":
    # The `argparse` library is used to create a user-friendly command-line interface.
    parser = argparse.ArgumentParser(description="Manage the CBRE report download logs.")
    # Subparsers allow us to create different commands (like `promote` and `mark-irrelevant`).
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --- Define the 'promote' command and its arguments ---
    parser_promote = subparsers.add_parser("promote", help="Promote a URL from failed to the success log after manual correction.")
    parser_promote.add_argument("url", type=str, help="The full URL of the report to promote.")
    parser_promote.add_argument("filename", type=str, help="The new, correct filename assigned to the report.")

    # --- Define the 'mark-irrelevant' command and its arguments ---
    parser_irrelevant = subparsers.add_parser("mark-irrelevant", help="Mark a URL in the failed log as irrelevant.")
    parser_irrelevant.add_argument("url", type=str, help="The full URL of the report to mark as irrelevant.")

    # Parse the arguments provided by the user in the terminal.
    args = parser.parse_args()

    # Call the appropriate function based on the command the user entered.
    if args.command == "promote":
        promote_to_success(args.url, args.filename)
    elif args.command == "mark-irrelevant":
        mark_as_irrelevant(args.url)
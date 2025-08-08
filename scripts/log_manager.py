import os
import json
import argparse

# Get the directory of the current script (e.g., .../your_project/scripts)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to the project's root directory
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
# Define the base path relative to the project root. This is now always correct.
BASE_REPORT_PATH = os.path.join(PROJECT_ROOT, "CBRE_Reports")

SUCCESS_LOG_PATH = os.path.join(BASE_REPORT_PATH, "download_log.json")
FAILED_LOG_PATH = os.path.join(BASE_REPORT_PATH, "failed_log.json")

def promote_to_success(url_to_promote: str, new_filename: str):
    """
    Moves a URL from the failed log to the success log.

    This should be run manually after you have moved and renamed a file
    from the 'failed_downloads' folder to its correct organized directory.
    """
    # Load both logs
    failed_log = {}
    if os.path.exists(FAILED_LOG_PATH):
        with open(FAILED_LOG_PATH, 'r') as f:
            try:
                failed_log = json.load(f)
            except json.JSONDecodeError:
                pass # File is empty or corrupt

    success_log = {}
    if os.path.exists(SUCCESS_LOG_PATH):
        with open(SUCCESS_LOG_PATH, 'r') as f:
            try:
                success_log = json.load(f)
            except json.JSONDecodeError:
                pass # File is empty or corrupt

    # Check if the URL exists in the failed log
    if url_to_promote not in failed_log:
        print(f"\n❌ Error: URL not found in the failed log.\n'{url_to_promote}'")
        return

    # Remove from failed log
    reason = failed_log.pop(url_to_promote)
    print(f"✓ Removed from failed log (Reason was: {reason})")

    # Add to success log
    success_log[url_to_promote] = new_filename
    print(f"✓ Added to success log with filename '{new_filename}'")

    # Save both files
    with open(FAILED_LOG_PATH, 'w') as f:
        json.dump(failed_log, f, indent=4)
        print(f"✓ Updated '{FAILED_LOG_PATH}'")

    with open(SUCCESS_LOG_PATH, 'w') as f:
        json.dump(success_log, f, indent=4)
        print(f"✓ Updated '{SUCCESS_LOG_PATH}'")

    print("\n✅ Promotion complete!")


# --- HOW TO RUN THIS SCRIPT ---
#
# 1. Open your terminal or command prompt.
# 2. Navigate to the directory where this script is located.
# 3. After you manually fix a file from the 'failed_downloads' folder,
#    run the script using the following format, replacing the placeholders
#    with the actual URL and the new, correct filename.
#
# ----------------- USAGE EXAMPLE -----------------
# python log_manager.py "https://www.cbre.com/insights/figures/q1-2025-us-net-lease-investment-figures" "US Net-Lease Investment 2025 Q1.pdf"
# -------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Manage the CBRE report download logs. Use this to promote a URL from the failed log to the success log after manual correction."
    )
    parser.add_argument(
        "url",
        type=str,
        help="The full URL of the report to promote."
    )
    parser.add_argument(
        "filename",
        type=str,
        help="The new, correct filename you have assigned to the downloaded report (e.g., 'Kansas City 2025 Q2.pdf')."
    )

    args = parser.parse_args()

    promote_to_success(args.url, args.filename)
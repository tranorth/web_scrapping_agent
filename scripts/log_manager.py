import os
import json
import argparse

# --- Robust Path Definition ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BASE_REPORT_PATH = os.path.join(PROJECT_ROOT, "CBRE_Reports")

SUCCESS_LOG_PATH = os.path.join(BASE_REPORT_PATH, "download_log.json")
FAILED_LOG_PATH = os.path.join(BASE_REPORT_PATH, "failed_log.json")
IRRELEVANT_LOG_PATH = os.path.join(BASE_REPORT_PATH, "irrelevant_log.json")

def _load_log(path):
    """Safely loads a JSON log file."""
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def promote_to_success(url_to_promote: str, new_filename: str):
    """Moves a URL from the failed log to the success log."""
    failed_log = _load_log(FAILED_LOG_PATH)
    success_log = _load_log(SUCCESS_LOG_PATH)

    if url_to_promote not in failed_log:
        print(f"\n❌ Error: URL not found in the failed log.\n'{url_to_promote}'")
        return

    reason = failed_log.pop(url_to_promote)
    success_log[url_to_promote] = new_filename

    with open(FAILED_LOG_PATH, 'w') as f:
        json.dump(failed_log, f, indent=4)
    with open(SUCCESS_LOG_PATH, 'w') as f:
        json.dump(success_log, f, indent=4)

    print("\n✅ Promotion complete!")
    print(f"✓ Moved '{url_to_promote[:50]}...' to success log.")

def mark_as_irrelevant(url_to_mark: str):
    """Moves a URL from the failed log to the irrelevant log."""
    failed_log = _load_log(FAILED_LOG_PATH)
    irrelevant_log = _load_log(IRRELEVANT_LOG_PATH)

    if url_to_mark not in failed_log:
        print(f"\n❌ Error: URL not found in the failed log.\n'{url_to_mark}'")
        return

    reason = failed_log.pop(url_to_mark)
    irrelevant_log[url_to_mark] = "Marked as irrelevant by user."

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage the CBRE report download logs.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --- 'promote' command ---
    parser_promote = subparsers.add_parser("promote", help="Promote a URL from failed to the success log after manual correction.")
    parser_promote.add_argument("url", type=str, help="The full URL of the report to promote.")
    parser_promote.add_argument("filename", type=str, help="The new, correct filename assigned to the report.")

    # --- 'mark-irrelevant' command ---
    parser_irrelevant = subparsers.add_parser("mark-irrelevant", help="Mark a URL in the failed log as irrelevant.")
    parser_irrelevant.add_argument("url", type=str, help="The full URL of the report to mark as irrelevant.")

    args = parser.parse_args()

    if args.command == "promote":
        promote_to_success(args.url, args.filename)
    elif args.command == "mark-irrelevant":
        mark_as_irrelevant(args.url)
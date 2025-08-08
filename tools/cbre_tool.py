# tools/cbre_tool.py

# Import standard Python libraries for handling dates, files, and errors.
import datetime
import os
import traceback
# Import typing utilities for defining data structures and types.
from typing import Type, Optional, Literal
# Import Pydantic for data validation and defining the tool's input schema.
from pydantic.v1 import BaseModel, Field 
# Import the base class for all LangChain tools.
from langchain.tools import BaseTool

# Import our custom-built modules.
from scrapers.web_scraper import Scraper  # The Selenium scraper for interacting with the website.
from tools.download_tools import CbreTitleParserTool, CbrePDFDownloaderTool # The sub-tools for parsing titles and downloading files.
# Import all the utility functions for reading and writing to our log files.
from utils.file_utils import check_existing_files, load_download_log, update_download_log, load_failed_log, update_failed_log, load_irrelevant_log, update_irrelevant_log

# --- Robust Path Definition ---
# This section ensures that the 'CBRE_Reports' folder is always created in the
# project's main root directory, regardless of where the script is executed from.
# This prevents errors caused by relative paths.

# Get the absolute path to this file's directory (e.g., .../your_project/tools).
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to the project's root directory.
PROJECT_ROOT = os.path.dirname(TOOL_DIR)
# Define the base path for all report-related storage relative to the project root.
BASE_REPORT_PATH = os.path.join(PROJECT_ROOT, "CBRE_Reports")


class ReportArchiveInput(BaseModel):
    """
    Defines the input arguments for the CbreReportArchiverTool using Pydantic.
    This schema allows the LangChain agent to understand what inputs the tool accepts,
    their types, descriptions, and default values.
    """
    country: str = Field(
        default="United States",
        description="The country to filter by."
    )
    property_type: Literal["Industrial and Logistics", "Office", "Retail", "Multifamily"] = Field(
        default="Industrial and Logistics",
        description="The specific property type to filter by."
    )
    year: Optional[int] = Field(
        default=None, 
        description="The four-digit year. If omitted, all years are considered."
    )
    period: Optional[str] = Field(
        default=None, 
        description="The period (e.g., 'H1', 'Q1'). If omitted, all periods are considered."
    )


class CbreReportArchiverTool(BaseTool):
    """
    This is the main tool class that orchestrates the entire process.
    The LangChain agent interacts directly with this tool.
    """
    # The 'name' is a unique identifier for the tool.
    name: str = "cbre_report_archiver"
    # The 'description' is crucial. The LLM reads this to decide if this tool
    # is the right one to use for the user's request.
    description: str = (
        "Searches for and archives CBRE market reports. "
        "If the user's request is broad or does not specify filters like country, "
        "property type, year, or period, this tool MUST be called with its "
        "default parameters to perform a general search."
    )
    # This links the tool to its input schema defined above.
    args_schema: Type[BaseModel] = ReportArchiveInput

    # The _run method contains the core logic that is executed when the agent calls the tool.
    def _run(
        self,
        country: str = "United States",
        property_type: str = "Industrial and Logistics",
        year: Optional[int] = None,
        period: Optional[str] = None,
    ) -> str:
        
        # --- 1. Initialization and State Loading ---
        
        # Ensure the main storage directory exists.
        if not os.path.exists(BASE_REPORT_PATH):
            os.makedirs(BASE_REPORT_PATH)

        # Define the full paths to each of our state-management log files.
        SUCCESS_LOG_PATH = os.path.join(BASE_REPORT_PATH, "download_log.json")
        FAILED_LOG_PATH = os.path.join(BASE_REPORT_PATH, "failed_log.json")
        IRRELEVANT_LOG_PATH = os.path.join(BASE_REPORT_PATH, "irrelevant_log.json")
        
        # Create lists to track the outcomes of the current run.
        newly_downloaded_files = []
        failed_downloads = []
        partially_downloaded_files = []

        # Load the URLs from all three logs to build a comprehensive set of reports to ignore.
        # This prevents the tool from re-processing reports that are already handled.
        successful_urls = load_download_log(SUCCESS_LOG_PATH)
        failed_urls = set(load_failed_log(FAILED_LOG_PATH).keys())
        irrelevant_urls = load_irrelevant_log(IRRELEVANT_LOG_PATH)
        urls_to_ignore = successful_urls.union(failed_urls, irrelevant_urls)
        print(f"🧠 Found {len(successful_urls)} successful, {len(failed_urls)} failed, and {len(irrelevant_urls)} irrelevant reports in logs. They will be skipped.")

        # --- 2. Web Scraping ---

        scraper = Scraper(headless=True)
        # A `try...finally` block ensures that the browser is always closed, even if errors occur.
        try:
            # Prepare the website for scraping (accept cookies, switch to iframe, etc.).
            if not scraper.setup_cbre_insights_page("https://www.cbre.com/insights#market-reports"):
                return "Error: Could not set up the CBRE insights page."

            # Apply the filters based on the tool's input arguments.
            scraper.apply_filter(filter_name="Property Type", filter_value=property_type)
            scraper.apply_filter(filter_name="Country", filter_value=country)
            scraper.sort_results_by("Most Recent")

            # Configure the scraping parameters.
            enable_smart_stopping = bool(year)
            search_terms = []
            
            scrape_config = {
                "content_container_selector": ".coveo-result-list-container",
                "link_selector": ".coveo-result-list-container a",
                "search_terms": search_terms,
                "next_page_selector": "li.coveo-pager-next span[role='button']",
                "enable_early_stopping": enable_smart_stopping, 
                "target_year": year, 
                "target_period": period
            }
            
            # Execute the scraping process to get all report URLs and titles from the website.
            report_urls_with_titles = scraper.extract_links_from_pages(scrape_config)

            if not report_urls_with_titles:
                return "No reports found on the website matching the criteria."

            # Filter the scraped list against our ignore list to find only new reports.
            new_reports_to_process = {
                url: title
                for url, title in report_urls_with_titles.items()
                if url not in urls_to_ignore
            }

            if not new_reports_to_process:
                return "Process complete. No new reports to download."

            print(f"\n--- Found {len(new_reports_to_process)} new reports to process ---")
            
            # --- 3. Processing and Downloading ---

            # Parse all the new titles in a single batch for efficiency.
            titles_to_parse = list(new_reports_to_process.values())
            title_parser = CbreTitleParserTool()
            parsed_reports_data = title_parser._run(titles=titles_to_parse)

            # Create a map to easily find a report's URL from its title.
            url_map = {title: url for url, title in new_reports_to_process.items()}
            # Initialize the downloader tool.
            downloader = CbrePDFDownloaderTool(driver=scraper.driver, download_dir=scraper.download_dir)

            # Loop through each new report to download and process it.
            for report_data in parsed_reports_data:
                report_url = url_map.get(report_data.get('original_title'))
                if not report_url:
                    continue
                
                # Call the downloader sub-tool, which returns a status and a result message.
                status, data = downloader._run(
                    report_url=report_url, 
                    parsed_info=report_data, 
                    base_save_path=BASE_REPORT_PATH
                )

                # Handle the outcome based on the status returned by the downloader.
                if status == "success":
                    # If successful, add to the success list and update the success log.
                    final_filename = data
                    update_download_log(SUCCESS_LOG_PATH, report_url, final_filename)
                    newly_downloaded_files.append(final_filename)
                elif status == "partial_success":
                    # If partially successful, add to the partial list and update the failed log.
                    print(f"      - ⚠️  {data}")
                    partially_downloaded_files.append(data)
                    update_failed_log(FAILED_LOG_PATH, report_url, "Partial Success - Parsing/Organizing Failed")
                else: # status == "error"
                    # If it's a total error, add to the error list and update the failed log.
                    print(f"      - ❌ Download failed for {report_url}")
                    failed_downloads.append({"url": report_url, "error": data})
                    update_failed_log(FAILED_LOG_PATH, report_url, data)

            # --- 4. Final Reporting ---
            
            # Build a final summary string based on the outcomes of the run.
            summary_parts = []
            if newly_downloaded_files:
                summary_parts.append(f"Successfully downloaded and organized {len(newly_downloaded_files)} new reports.")
            if partially_downloaded_files:
                summary_parts.append(f"{len(partially_downloaded_files)} reports were downloaded but could not be organized. They have been moved to the 'CBRE_Reports/failed_downloads' folder for your manual review.")
            if failed_downloads:
                summary_parts.append(f"Failed to download {len(failed_downloads)} reports entirely.")
            
            if not summary_parts:
                return "Process complete. No new reports to download."
            
            # Return the final, comprehensive summary to the agent.
            return " ".join(summary_parts)

        except Exception as e:
            # A top-level error handler to catch any unexpected crashes.
            exc_info = traceback.format_exc()
            error_message = (
                f"FATAL: An unexpected error occurred in CbreReportArchiverTool._run (cbre_tool.py).\n"
                f"Error: {e}\n\n"
                f"This error was not handled by the tool's internal logic and points to a potential bug.\n\n"
                f"Full Traceback:\n{exc_info}"
            )
            print(error_message)
            return error_message
        finally:
            # This block ALWAYS runs, ensuring the browser is closed to prevent memory leaks.
            scraper.close()
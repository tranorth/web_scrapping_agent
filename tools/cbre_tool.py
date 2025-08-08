import datetime
import os
import traceback
from typing import Type, Optional, Literal
from pydantic.v1 import BaseModel, Field 
from langchain.tools import BaseTool

# Your existing, proven components
from scrapers.web_scraper import Scraper
from tools.download_tools import CbreTitleParserTool, CbrePDFDownloaderTool
from utils.file_utils import check_existing_files, load_download_log, update_download_log


class ReportArchiveInput(BaseModel):
    """Input schema for the CbreReportArchiverTool."""
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
    A tool that finds, parses, and downloads CBRE market reports.
    It defaults to searching for 'Industrial and Logistics' reports in the 'United States'
    for recent years unless specified otherwise in the prompt.
    """
    name: str = "cbre_report_archiver"
    description: str = (
        "Searches for and archives CBRE market reports. "
        "If the user's request is broad or does not specify filters like country, "
        "property type, year, or period, this tool MUST be called with its "
        "default parameters to perform a general search."
    )
    args_schema: Type[BaseModel] = ReportArchiveInput

    # --- MODIFIED: The complete, updated _run method ---
    def _run(
        self,
        country: str = "United States",
        property_type: str = "Industrial and Logistics",
        year: Optional[int] = None,
        period: Optional[str] = None,
    ) -> str:
        
        BASE_REPORT_PATH = "CBRE_Reports"
        if not os.path.exists(BASE_REPORT_PATH):
            os.makedirs(BASE_REPORT_PATH)
        LOG_FILE_PATH = os.path.join(BASE_REPORT_PATH, "download_log.json")
        
        newly_downloaded_files = []
        failed_downloads = []

        downloaded_urls = load_download_log(LOG_FILE_PATH)
        print(f"🧠 Found {len(downloaded_urls)} previously downloaded reports in the log.")

        scraper = Scraper(headless=True)
        try:
            if not scraper.setup_cbre_insights_page("https://www.cbre.com/insights#market-reports"):
                return "Error: Could not set up the CBRE insights page."

            scraper.apply_filter(filter_name="Property Type", filter_value=property_type)
            scraper.apply_filter(filter_name="Country", filter_value=country)
            scraper.sort_results_by("Most Recent")

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
            
            report_urls_with_titles = scraper.extract_links_from_pages(scrape_config)

            if not report_urls_with_titles:
                return "No reports found on the website matching the criteria."

            new_reports_to_process = {
                url: title
                for url, title in report_urls_with_titles.items()
                if url not in downloaded_urls
            }

            if not new_reports_to_process:
                return "Process complete. No new reports to download."

            print(f"\n--- Found {len(new_reports_to_process)} new reports to process ---")
            
            titles_to_parse = list(new_reports_to_process.values())
            title_parser = CbreTitleParserTool()
            parsed_reports_data = title_parser._run(titles=titles_to_parse)

            url_map = {title: url for url, title in new_reports_to_process.items()}
            downloader = CbrePDFDownloaderTool(driver=scraper.driver, download_dir=scraper.download_dir)

            for report_data in parsed_reports_data:
                report_url = url_map.get(report_data.get('original_title'))
                if not report_url:
                    continue

                if period and report_data.get('period') != period:
                    continue
                
                status, data = downloader._run(
                    report_url=report_url, 
                    parsed_info=report_data, 
                    base_save_path=BASE_REPORT_PATH
                )

                if status == "success":
                    final_filename = data
                    update_download_log(LOG_FILE_PATH, report_url, final_filename)
                    newly_downloaded_files.append(final_filename)
                else:
                    print(f"      - ❌ Download failed for {report_url}")
                    failed_downloads.append({"url": report_url, "error": data})

            summary_parts = []
            if newly_downloaded_files:
                summary_parts.append(f"Successfully downloaded {len(newly_downloaded_files)} new reports: {', '.join(sorted(newly_downloaded_files))}.")
            
            if failed_downloads:
                summary_parts.append(f"Failed to download {len(failed_downloads)} reports.")
            
            if not newly_downloaded_files and not failed_downloads:
                return "Process complete. All matching reports were already downloaded."
            
            return " ".join(summary_parts)

        except Exception as e:
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
            scraper.close()





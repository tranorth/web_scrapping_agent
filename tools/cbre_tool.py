import datetime
from typing import Type, Optional, Literal
from pydantic.v1 import BaseModel, Field
from langchain.tools import BaseTool

# Your existing, proven components
from scrapers.web_scraper import Scraper
from tools.download_tools import CbreTitleParserTool, CbrePDFDownloaderTool
from utils.file_utils import check_existing_files


class ReportArchiveInput(BaseModel):
    """Input schema for the CbreReportArchiverTool."""
    # --- All fields now have defaults for autonomous operation ---
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

    def _run(
        self,
        country: str = "United States",
        property_type: str = "Industrial and Logistics",
        year: Optional[int] = None,
        period: Optional[str] = None,
    ) -> str:
        
        BASE_REPORT_PATH = "CBRE_Reports"
        existing_files = check_existing_files(BASE_REPORT_PATH)
        newly_downloaded_files = []

        scraper = Scraper(headless=True)
        downloader = CbrePDFDownloaderTool(driver=scraper.driver, download_dir=scraper.download_dir)
        
        try:
            if not scraper.setup_cbre_insights_page("https://www.cbre.com/insights#market-reports"):
                return "Error: Could not set up the CBRE insights page."

            # --- This logic is now outside the loop for efficiency ---
            scraper.apply_filter(filter_name="Property Type", filter_value=property_type)
            scraper.apply_filter(filter_name="Country", filter_value=country)
            scraper.sort_results_by("Most Recent")
            
            # --- This is the new "smart" configuration ---
            # If the user gives a specific year and period, we enable early stopping.
            # Otherwise, we disable it to get ALL reports.
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
            
            # --- This is your original, complete workflow ---
            # It now runs with the smart configuration.
            report_urls_with_titles = scraper.extract_links_from_pages(scrape_config)

            if not report_urls_with_titles:
                return "No new reports found matching the criteria on the website."
            
            title_parser = CbreTitleParserTool()
            parsed_reports_data = title_parser._run(titles=list(report_urls_with_titles.values()))
            url_map = {title: url for url, title in report_urls_with_titles.items()}

            # New: If a specific period was requested, filter the parsed results
            reports_to_process = []
            if period:
                 reports_to_process = [r for r in parsed_reports_data if r.get('period') == period]
            else:
                 reports_to_process = parsed_reports_data

            for report_data in reports_to_process:
                market = report_data['market_name'].replace(' ', '_').replace('/', '_').replace('.', '')
                filename = f"{market}_{report_data['year']}_{report_data['period']}.pdf"
                
                if filename in existing_files:
                    continue
                
                report_url = url_map.get(report_data['original_title'])
                if not report_url:
                    continue

                result = downloader._run(report_url=report_url, parsed_info=report_data, base_save_path=BASE_REPORT_PATH)
                if "Success" in result:
                    newly_downloaded_files.append(filename)
            
            if newly_downloaded_files:
                return f"Success! Downloaded {len(newly_downloaded_files)} new reports: {', '.join(sorted(newly_downloaded_files))}"
            else:
                return "Process complete. All matching reports are already present."

        except Exception as e:
            return f"An error occurred: {e}"
        finally:
            scraper.close()
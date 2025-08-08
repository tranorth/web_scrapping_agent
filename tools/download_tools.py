# tools/download_tools.py

# Import standard Python libraries
import os
import json
import glob
import shutil
import time
import requests
import traceback
from typing import Type, Any, List, Dict, Tuple

# Import Pydantic for data validation and schema definition
from pydantic.v1 import BaseModel, Field
# Import the base class for creating LangChain tools
from langchain.tools import BaseTool
# Import the specific LLM for parsing titles
from langchain_google_vertexai import ChatVertexAI
# Import Selenium components for web browser automation
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# A constant User-Agent string to make our web requests look like they're coming from a real browser.
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
}

# --- Pydantic Schemas for Structured Output ---
# These classes define the expected structure of the data that the LLM will extract.

class ReportInfo(BaseModel):
    """Defines the structure for a single parsed report title."""
    original_title: str = Field(description="The original, unmodified title of the report.")
    market_name: str = Field(description="The primary geographical location of the report.")
    year: str = Field(description="The four-digit year of the report.")
    period: str = Field(description="The report's period, such as 'Q1', 'Q2', 'Q3', 'Q4', 'H1', or 'H2'.")

class ReportInfoList(BaseModel):
    """Defines a list that will contain multiple ReportInfo objects."""
    reports: List[ReportInfo]


class CbreTitleParserTool(BaseTool):
    """
    A specialized sub-tool that uses an LLM to parse a list of unstructured report titles
    and extract structured information (market, year, period) from them.
    """
    name: str = "cbre_title_parser"
    description: str = "Efficiently parses a list of CBRE report titles to extract structured data."
    
    class ParserInput(BaseModel):
        """Defines the input for this tool: a list of strings."""
        titles: List[str]
    args_schema: Type[BaseModel] = ParserInput

    def _run(self, titles: List[str]) -> List[Dict]:
        """The main execution logic for the title parser."""
        print(f"\n🧠 Sending {len(titles)} titles to the AI for parsing in a single batch...")
        # Initialize the Gemini LLM.
        llm = ChatVertexAI(model="gemini-1.5-pro-preview-0409", temperature=0)
        # Configure the LLM to return output that is guaranteed to match the 'ReportInfoList' schema.
        structured_llm = llm.with_structured_output(ReportInfoList)
        # Format the list of titles into a numbered string to include in the prompt.
        titles_str = "\n".join([f"{i+1}. {title}" for i, title in enumerate(titles)])
        
        # This prompt contains the instructions for the LLM, telling it exactly how to parse the titles.
        prompt = f"""
        Analyze each real estate report title from the numbered list below.
        For each title, extract the 'original_title', 'market_name', 'year', and 'period'.
        - The 'market_name' is the main geographical location.
        - The 'period' is the time designation (e.g., 'Q1', 'H1'). Extract it exactly as it appears.
        - The 'original_title' must be the exact, unmodified title from the list.
        - Exclude generic words like "Industrial", "Figures", "Report", "Snapshot" from the 'market_name'.

        List of Titles:
        {titles_str}
        
        Return ONLY a raw JSON object with a single key "reports" which is a list of objects.
        """
        try:
            # Send the prompt to the LLM and get the structured result.
            result = structured_llm.invoke(prompt)
            print("✓ AI parsing successful.")
            # Convert the Pydantic objects back into standard Python dictionaries.
            return [report.dict() for report in result.reports]
        except Exception as e:
            print(f"❌ AI parsing failed: {e}")
            return []


class CbrePDFDownloaderTool(BaseTool):
    """
    A sub-tool that handles the entire process of downloading a single PDF.
    It takes the parsed info and a URL, uses Selenium to download the file,
    and then organizes it based on the parsed info.
    """
    name: str = "cbre_pdf_downloader"
    description: str = "Given structured report info, this tool downloads the corresponding PDF and saves it."
    
    class DownloaderInput(BaseModel):
        """Defines the inputs for this tool."""
        report_url: str
        parsed_info: dict
        base_save_path: str
    args_schema: Type[BaseModel] = DownloaderInput
    
    # These attributes are passed in when the tool is initialized in 'cbre_tool.py'.
    driver: Any  # The Selenium WebDriver instance.
    download_dir: str # The path to the temporary download folder.

    def _run(self, report_url: str, parsed_info: dict, base_save_path: str) -> Tuple[str, str]:
        """The main execution logic for the downloader."""
        try:
            # --- Step 1: Download the file to a temporary location FIRST ---
            # This makes the process more robust. We confirm the download before trying to organize it.
            self.driver.get(report_url)
            # Wait for the download link to appear on the page.
            download_element = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.cbre-c-download"))
            )
            # Clear any old files from the temporary download directory.
            for f in os.listdir(self.download_dir):
                os.remove(os.path.join(self.download_dir, f))
            # Click the download link.
            download_element.click()

            # Wait for the download to complete (up to 30 seconds).
            downloaded_pdf_path = None
            download_wait_time = 0
            while download_wait_time < 30:
                # Check if a .pdf file has appeared in the temp folder.
                if temp_path := next((os.path.join(self.download_dir, f) for f in os.listdir(self.download_dir) if f.endswith('.pdf')), None):
                    downloaded_pdf_path = temp_path
                    break  # Exit the loop once the PDF is found.
                time.sleep(1)
                download_wait_time += 1
            
            # If no PDF was found after 30 seconds, return a timeout error.
            if not downloaded_pdf_path:
                return "error", f"Download timed out for {report_url}"

            # --- Step 2: Now that the file is downloaded, try to process and move it ---
            # Safely get the parsed info, using empty strings as a default.
            raw_market_name = parsed_info.get('market_name', '').strip()
            year = parsed_info.get('year', '').strip()
            period = parsed_info.get('period', '').strip()

            # Check if the AI parsing was successful by seeing if we have all the key info.
            if not all([raw_market_name, year, period]):
                # If parsing failed, this is a "partial success".
                # The file is downloaded but can't be organized automatically.
                failed_folder = os.path.join(base_save_path, "failed_downloads", "Parsing_Error")
                os.makedirs(failed_folder, exist_ok=True)
                failed_filename = os.path.basename(downloaded_pdf_path)
                # Move the file to the 'failed_downloads' folder for manual review.
                shutil.move(downloaded_pdf_path, os.path.join(failed_folder, failed_filename))
                message = f"File '{failed_filename}' downloaded but couldn't be organized. Moved to '{failed_folder}' for manual review."
                return "partial_success", message

            # --- This part only runs if parsing was successful ---
            # Sanitize the filename to remove characters that are illegal in Windows file paths.
            invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
            sanitized_market_name = raw_market_name
            for char in invalid_chars:
                sanitized_market_name = sanitized_market_name.replace(char, ' ')

            # Create the clean filename and the final organized folder path.
            market = sanitized_market_name
            filename = f"{market} {year} {period}.pdf"
            folder_path = os.path.join(base_save_path, str(year), f"{year} {period}")
            final_save_path = os.path.join(folder_path, filename)
            
            # Create the destination folder if it doesn't exist.
            os.makedirs(folder_path, exist_ok=True)
            # Move the file from the temporary folder to its final, organized location.
            shutil.move(downloaded_pdf_path, final_save_path)
            print(f"   ✓ Success: Moved and saved '{filename}' to '{folder_path}'")
            return "success", filename

        except Exception as e:
            # This is a general-purpose error handler to catch any unexpected crashes.
            exc_info = traceback.format_exc()
            error_message = (
                f"An unexpected exception occurred in CbrePDFDownloaderTool._run.\n"
                f"URL: {report_url}\n"
                f"Details: {e}\n\nTraceback:\n{exc_info}"
            )
            return "error", error_message
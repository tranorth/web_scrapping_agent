# download_tools.py

import os
import json
import glob
import shutil
import time
import requests
import traceback
from typing import Type, Any, List, Dict, Tuple
from pydantic.v1 import BaseModel, Field
from langchain.tools import BaseTool
from langchain_google_vertexai import ChatVertexAI
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ADD THIS HEADER TO MIMIC A BROWSER
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
}

class ReportInfo(BaseModel):
    original_title: str = Field(description="The original, unmodified title of the report.")
    market_name: str = Field(description="The primary geographical location of the report.")
    year: str = Field(description="The four-digit year of the report.")
    period: str = Field(description="The report's period, such as 'Q1', 'Q2', 'Q3', 'Q4', 'H1', or 'H2'.")

class ReportInfoList(BaseModel):
    reports: List[ReportInfo]

class CbreTitleParserTool(BaseTool):
    name: str = "cbre_title_parser"
    description: str = "Efficiently parses a list of CBRE report titles to extract structured data."
    class ParserInput(BaseModel):
        titles: List[str]
    args_schema: Type[BaseModel] = ParserInput

    def _run(self, titles: List[str]) -> List[Dict]:
        print(f"\n🧠 Sending {len(titles)} titles to the AI for parsing in a single batch...")
        llm = ChatVertexAI(model="gemini-2.5-pro", temperature=0)
        structured_llm = llm.with_structured_output(ReportInfoList)
        titles_str = "\n".join([f"{i+1}. {title}" for i, title in enumerate(titles)])
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
            result = structured_llm.invoke(prompt)
            print("✓ AI parsing successful.")
            return [report.dict() for report in result.reports]
        except Exception as e:
            print(f"❌ AI parsing failed: {e}")
            return []

class CbrePDFDownloaderTool(BaseTool):
    # (This class is updated)
    name: str = "cbre_pdf_downloader"
    description: str = "Given structured report info, this tool downloads the corresponding PDF and saves it."
    class DownloaderInput(BaseModel):
        report_url: str
        parsed_info: dict
        base_save_path: str
    args_schema: Type[BaseModel] = DownloaderInput
    driver: Any
    download_dir: str

    def _run(self, report_url: str, parsed_info: dict, base_save_path: str) -> Tuple[str, str]:
        try:
            # --- Step 1: Download the file to a temporary location FIRST ---
            self.driver.get(report_url)
            download_element = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.cbre-c-download"))
            )
            for f in os.listdir(self.download_dir):
                os.remove(os.path.join(self.download_dir, f))
            download_element.click()

            downloaded_pdf_path = None
            download_wait_time = 0
            while download_wait_time < 30:
                if temp_path := next((os.path.join(self.download_dir, f) for f in os.listdir(self.download_dir) if f.endswith('.pdf')), None):
                    downloaded_pdf_path = temp_path
                    break  # Exit loop once PDF is found
                time.sleep(1)
                download_wait_time += 1

            if not downloaded_pdf_path:
                return "error", f"Download timed out for {report_url}"

            # --- Step 2: Now that the file is downloaded, try to process and move it ---
            raw_market_name = parsed_info.get('market_name', '').strip()
            year = parsed_info.get('year', '').strip()
            period = parsed_info.get('period', '').strip()

            # Check if the AI parsing was successful
            if not all([raw_market_name, year, period]):
                # This is a "partial success". The file is downloaded but can't be organized.
                failed_folder = os.path.join(base_save_path, "failed_downloads", "Parsing_Error")
                os.makedirs(failed_folder, exist_ok=True)
                failed_filename = os.path.basename(downloaded_pdf_path)
                shutil.move(downloaded_pdf_path, os.path.join(failed_folder, failed_filename))
                message = f"File '{failed_filename}' downloaded but couldn't be organized. Moved to '{failed_folder}' for manual review."
                return "partial_success", message

            # --- This part only runs if parsing was successful ---
            invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
            sanitized_market_name = raw_market_name
            for char in invalid_chars:
                sanitized_market_name = sanitized_market_name.replace(char, ' ')

            market = sanitized_market_name
            filename = f"{market} {year} {period}.pdf"
            folder_path = os.path.join(base_save_path, str(year), f"{year} {period}")
            final_save_path = os.path.join(folder_path, filename)

            os.makedirs(folder_path, exist_ok=True)
            shutil.move(downloaded_pdf_path, final_save_path)
            print(f"   ✓ Success: Moved and saved '{filename}' to '{folder_path}'")
            return "success", filename

        except Exception as e:
            # This will catch any other unexpected error during the process
            exc_info = traceback.format_exc()
            error_message = (
                f"An unexpected exception occurred in CbrePDFDownloaderTool._run.\n"
                f"URL: {report_url}\n"
                f"Details: {e}\n\nTraceback:\n{exc_info}"
            )
            return "error", error_message
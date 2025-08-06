# download_tools.py

import os
import json
import glob
import shutil
import time
import requests
from typing import Type, Any, List, Dict
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

    def _run(self, report_url: str, parsed_info: dict, base_save_path: str):
        market = parsed_info['market_name'].replace('.', '')
        year = parsed_info['year']
        period = parsed_info['period']
        
        filename = f"{market} {year} {period}.pdf"
        folder_path = os.path.join(base_save_path, str(year), f"{year} {period}")
        final_save_path = os.path.join(folder_path, filename)

        try:
            # 1. Navigate to the page
            self.driver.get(report_url)
            download_element = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.cbre-c-download"))
            )
            
            # 2. Clear the temp download folder before clicking
            for f in os.listdir(self.download_dir):
                os.remove(os.path.join(self.download_dir, f))

            # 3. Click the link to trigger the automatic download
            download_element.click()

            # 4. Wait for the download to complete
            # This loop waits until the .crdownload file is gone and the .pdf is present
            download_wait_time = 0
            while download_wait_time < 30: # 30-second timeout
                # Search for files with .crdownload (in-progress) or .pdf extensions
                downloaded_files = glob.glob(os.path.join(self.download_dir, '*.*'))
                if any('.crdownload' in f for f in downloaded_files):
                    time.sleep(1)
                    download_wait_time += 1
                elif any('.pdf' in f for f in downloaded_files):
                    # Find the downloaded PDF
                    downloaded_pdf = [f for f in downloaded_files if f.endswith('.pdf')][0]
                    print(f"✓ Download complete: {os.path.basename(downloaded_pdf)}")
                    
                    # 5. Create final destination folder and move the file
                    os.makedirs(folder_path, exist_ok=True)
                    shutil.move(downloaded_pdf, final_save_path)
                    
                    return f"Success: Moved and saved '{filename}'"
                else: # No files found yet
                    time.sleep(1)
                    download_wait_time += 1
            return f"Error: Download timed out for {report_url}"

        except Exception as e:
            return f"Error downloading from {report_url}: {e}"
# web_scraper.py

import re
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

BY_MAP = {"ID": By.ID, "CSS_SELECTOR": By.CSS_SELECTOR, "CLASS_NAME": By.CLASS_NAME, "XPATH": By.XPATH}

class Scraper:
    """A reusable, intelligent web scraper class using Selenium."""

    def __init__(self, headless=True):
        self.download_dir = os.path.join(os.getcwd(), "temp_downloads")
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        service = Service()
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        print("🤖 Selenium WebDriver Initialized.")

    def setup_cbre_insights_page(self, url):
        """
        Navigates to the CBRE insights URL and reliably prepares the page for scraping.
        """
        self.driver.get(url)
        print(f"Navigated to: {url}")
        
        # Handle cookies if the banner appears
        try:
            cookie_button = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
            self.driver.execute_script("arguments[0].click();", cookie_button)
            print("✓ Accepted cookies.")
            time.sleep(1)
        except TimeoutException:
            print("! Cookie banner not found or already accepted.")
            
        # Explicitly click the "Market Reports" tab to ensure it's active
        try:
            market_reports_tab = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, "tab-market-reports")))
            market_reports_tab.click()
            print("✓ Clicked 'Market Reports' tab.")
            time.sleep(2) # Wait for tab content to load
        except TimeoutException:
            print("❌ Could not find the 'Market Reports' tab.")
            return False

        # Now that the tab is active, switch to the iframe
        try:
            iframe = WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='search-market-results']")))
            self.driver.switch_to.frame(iframe)
            print("✓ Switched to iframe.")
            time.sleep(3)
            return True
        except TimeoutException:
            print("❌ Could not find or switch to the reports iframe.")
            return False
    
    def discover_filters(self):
        """
        Scans the page to find all available filter categories and their options.
        
        Returns:
            dict: A dictionary where keys are filter names (e.g., "Region") 
                  and values are lists of available options (e.g., ["Americas", "APAC"]).
        """
        print("\n🔎 Discovering available filters...")
        available_filters = {}
        try:
            facet_containers = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.CoveoFacet"))
            )
            
            for container in facet_containers:
                filter_name = container.get_attribute("data-title")
                if not filter_name:
                    continue
                
                options = container.find_elements(By.CSS_SELECTOR, "li.coveo-facet-value")
                option_values = [opt.get_attribute("data-value") for opt in options if opt.get_attribute("data-value")]
                
                if option_values:
                    available_filters[filter_name] = option_values
            
            print("✓ Discovery complete.")
            return available_filters
        except TimeoutException:
            print("❌ Could not find filter panel to discover options.")
            return {}

    def apply_filter(self, filter_name, filter_value):
        """Applies a single filter by clicking its checkbox."""
        try:
            print(f"Applying filter: '{filter_name}' -> '{filter_value}'...")
            facet_xpath = f"//div[contains(@class, 'CoveoFacet') and @data-title='{filter_name}']"
            facet_container = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, facet_xpath)))
            
            value_xpath = f".//li[@data-value='{filter_value}']//div[@role='button']"
            filter_option = facet_container.find_element(By.XPATH, value_xpath)
            
            self.driver.execute_script("arguments[0].click();", filter_option)
            print("✓ Filter applied.")
            time.sleep(3)
        except (TimeoutException, NoSuchElementException):
            print(f"❌ Could not find or apply filter '{filter_name}' with value '{filter_value}'.")

    def sort_results_by(self, sort_caption):
        """Selects a sort option after scrolling it into view."""
        try:
            print(f"Sorting results by '{sort_caption}'...")
            toggle = self.driver.find_element(By.CSS_SELECTOR, "div.cbre-sort-toggle")
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", toggle)
            time.sleep(1)
            toggle.click()
            time.sleep(1)
            
            sort_option_xpath = f"//span[contains(@class, 'CoveoSort') and @data-caption='{sort_caption}']"
            sort_element = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, sort_option_xpath)))
            sort_element.click()
            print("✓ Sort option applied.")
            time.sleep(3)
        except (TimeoutException, NoSuchElementException):
            print(f"❌ Could not find or click sort option '{sort_caption}'.")

    def extract_links_from_pages(self, config):
        """
        Loops through pages, intelligently filtering by keywords, year, and period (Q or H),
        and stops early if possible when sorted by date.
        
        Returns:
            dict: A dictionary of {url: title} for all matching reports.
        """
        found_reports = {}
        page_count = 1
        
        enable_early_stopping = config.get("enable_early_stopping", False)
        target_year = config.get("target_year")
        target_period = config.get("target_period")

        # --- CORRECTED LOGIC ---
        # Convert year/period to a single number for easy comparison.
        # e.g., Q3 2024 -> 2024*4 + 3 = 8099
        # e.g., Q2 2024 -> 2024*4 + 2 = 8098
        period_to_value = {
            "Q1": 1, "Q2": 2, "H1": 2, "Q3": 3, "Q4": 4, "H2": 4,
            "YEAR-END": 4, "YE": 4, "FULL-YEAR": 4, "YEAREND": 4, 
            "year-end": 4, "yearend": 4
        }
        target_value = None
        if target_year:
            # If no period is given, we treat the target as the very beginning of that year.
            target_value = (target_year * 4) + period_to_value.get(target_period, 0)

        while True:
            print(f"📄 Scraping Page {page_count}...")
            should_stop_scraping = False
            try:
                WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, config["content_container_selector"])))
                links = self.driver.find_elements(By.CSS_SELECTOR, config["link_selector"])
            except TimeoutException:
                print(f"❌ Timed out waiting for content on page {page_count}. Halting.")
                break

            for link in links:
                link_text_raw = link.text
                link_text_lower = link_text_raw.lower()
                
                if all(kw.lower() in link_text_lower for kw in config["search_terms"]):
                    href = link.get_attribute('href')
                    if href and href not in found_reports:
                        keep_report = False
                        
                        report_year, report_period = None, None
                        match = re.search(r'(q([1-4])|h([1-2]))\s*(\d{4})', link_text_lower)
                        if match:
                            report_year = int(match.group(4))
                            report_period = match.group(1).upper()
                        
                        if not target_year:
                            keep_report = True
                        elif report_year and report_year == target_year:
                            if not target_period:
                                keep_report = True
                            elif report_period:
                                if report_period == target_period:
                                    keep_report = True
                                elif target_period in ["Q1", "Q2"] and report_period == "H1":
                                    keep_report = True
                                elif target_period in ["Q3", "Q4"] and report_period == "H2":
                                    keep_report = True
                        
                        if keep_report:
                            print(f"   ✅ Found matching report: {link_text_raw}")
                            found_reports[href] = link_text_raw
                            
                        if enable_early_stopping and target_year:
                        # --- CHANGE #2: A more powerful and flexible regular expression ---
                            match = re.search(r'(q[1-4]|h[1-2]|year-end|ye|full-year)\s*(\d{4})', link_text_lower)
                            
                            if match:
                                # --- CHANGE #3: Clean up the matched period to match our dictionary ---
                                report_period_raw = match.group(1)
                                report_period = report_period_raw.upper().replace('-', '')
                                report_year = int(match.group(2)) # Note: group index changed to 2

                                # The stopping logic itself is now correct and will be triggered properly.
                                if target_period and target_value:
                                    found_value = (report_year * 4) + period_to_value.get(report_period, 0)
                                    if found_value < target_value:
                                        print(f"\n   -- Found report from '{report_period_raw} {report_year}', which is older than target. Stopping early. --")
                                        should_stop_scraping = True
                                        break
                                elif report_year < target_year:
                                    print(f"\n   -- Found report from {report_year}, which is older than target year {target_year}. Stopping early. --")
                                    should_stop_scraping = True
                                    break

            if should_stop_scraping:
                break
            
            try:
                next_page_button = self.driver.find_element(By.CSS_SELECTOR, config["next_page_selector"])
                self.driver.execute_script("arguments[0].click();", next_page_button)
                page_count += 1
                print(f"   Navigating to page {page_count}...")
                time.sleep(3)
            except NoSuchElementException:
                print("\nNo 'Next Page' button found. Reached the end.")
                break
        
        return found_reports
    
    def close(self):
        """Closes the WebDriver."""
        if self.driver:
            self.driver.quit()
            print("🤖 WebDriver closed.")
        """Closes the WebDriver."""
        if self.driver:
            self.driver.quit()
            print("🤖 WebDriver closed.")
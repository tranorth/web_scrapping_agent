# scrapers/cbre_scaper.py

# Import necessary libraries
import re
import time  # For adding pauses (sleeps) to wait for the page to load

# Import the Selenium library, which automates web browser actions
from selenium.webdriver.common.by import By  # For selecting elements by ID, CSS Selector, etc.
from selenium.webdriver.support.ui import WebDriverWait  # For waiting until a condition is met
from selenium.webdriver.support import expected_conditions as EC  # Pre-defined conditions to wait for
from selenium.common.exceptions import TimeoutException, NoSuchElementException  # For handling errors

from scrapers.base_scraper import BaseScraper

class CbreScraper(BaseScraper):

    def __init__(self, headless=True):
        super().__init__(headless)

    def setup_cbre_insights_page(self, url):
        """
        Navigates to the CBRE insights URL and reliably prepares the page for scraping.
        This involves handling cookies, clicking the right tab, and switching to the iframe.
        """
        self.driver.get(url)
        print(f"Navigated to: {url}")
        
        # Use a try-except block to handle the cookie consent banner.
        try:
            # Wait up to 5 seconds for the cookie button to be clickable.
            cookie_button = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
            # Use JavaScript to click the button, which can be more reliable.
            self.driver.execute_script("arguments[0].click();", cookie_button)
            print("✓ Accepted cookies.")
            time.sleep(1)
        except TimeoutException:
            # If the button isn't found after 5 seconds, assume it's not there.
            print("! Cookie banner not found or already accepted.")
            
        # Click the "Market Reports" tab to reveal the report listings.
        try:
            market_reports_tab = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, "tab-market-reports")))
            market_reports_tab.click()
            print("✓ Clicked 'Market Reports' tab.")
            time.sleep(2)  # Wait for the tab's content to load.
        except TimeoutException:
            print("❌ Could not find the 'Market Reports' tab.")
            return False

        # The report listings are inside an iframe, so we must switch the driver's context to it.
        try:
            iframe = WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='search-market-results']")))
            self.driver.switch_to.frame(iframe)
            print("✓ Switched to iframe.")
            time.sleep(3)  # Wait for iframe content to be ready.
            return True
        except TimeoutException:
            print("❌ Could not find or switch to the reports iframe.")
            return False
    
    def discover_filters(self):
        """
        Scans the page to find all available filter categories and their options.
        This is useful for understanding what can be filtered without hardcoding values.
        """
        print("\n🔎 Discovering available filters...")
        available_filters = {}
        try:
            # Find all the main filter container elements.
            facet_containers = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.CoveoFacet"))
            )
            
            # Loop through each container to get its title and options.
            for container in facet_containers:
                filter_name = container.get_attribute("data-title") # e.g., "Property Type"
                if not filter_name:
                    continue
                
                # Find all clickable option elements within the container.
                options = container.find_elements(By.CSS_SELECTOR, "li.coveo-facet-value")
                option_values = [opt.get_attribute("data-value") for opt in options if opt.get_attribute("data-value")] # e.g., "Industrial and Logistics"
                
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
            # Use an XPath to precisely locate the filter container by its title.
            facet_xpath = f"//div[contains(@class, 'CoveoFacet') and @data-title='{filter_name}']"
            facet_container = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, facet_xpath)))
            
            # Within that container, find the specific option to click by its value.
            value_xpath = f".//li[@data-value='{filter_value}']//div[@role='button']"
            filter_option = facet_container.find_element(By.XPATH, value_xpath)
            
            # Use JavaScript to click, which can avoid issues with elements being obscured.
            self.driver.execute_script("arguments[0].click();", filter_option)
            print("✓ Filter applied.")
            time.sleep(3)  # Wait for the results to refresh.
        except (TimeoutException, NoSuchElementException):
            print(f"❌ Could not find or apply filter '{filter_name}' with value '{filter_value}'.")

    def sort_results_by(self, sort_caption):
        """Selects a sort option after scrolling it into view."""
        try:
            print(f"Sorting results by '{sort_caption}'...")
            # Find the dropdown menu for sorting.
            toggle = self.driver.find_element(By.CSS_SELECTOR, "div.cbre-sort-toggle")
            # Scroll the element into the center of the view to ensure it's clickable.
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", toggle)
            time.sleep(1)
            toggle.click() # Open the dropdown.
            time.sleep(1)
            
            # Find the specific sort option by its text content (caption).
            sort_option_xpath = f"//span[contains(@class, 'CoveoSort') and @data-caption='{sort_caption}']"
            sort_element = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, sort_option_xpath)))
            sort_element.click() # Click the option.
            print("✓ Sort option applied.")
            time.sleep(3)  # Wait for results to re-sort.
        except (TimeoutException, NoSuchElementException):
            print(f"❌ Could not find or click sort option '{sort_caption}'.")

    def extract_links_from_pages(self, config):
        """
        Loops through all pages of results, extracts the URLs and titles of reports,
        and intelligently stops early if it finds reports older than the target year/period.
        """
        found_reports = {}
        page_count = 1
        
        # Get configuration for early stopping to avoid unnecessary scraping.
        enable_early_stopping = config.get("enable_early_stopping", False)
        target_year = config.get("target_year")
        target_period = config.get("target_period")

        # This dictionary converts periods (Q1, H1, etc.) into numerical values.
        # This allows for easy comparison (e.g., is Q1 2024 older than Q3 2024?).
        period_to_value = {
            "Q1": 1, "Q2": 2, "H1": 2, "Q3": 3, "Q4": 4, "H2": 4,
            "YEAR-END": 4, "YE": 4, "FULL-YEAR": 4, "YEAREND": 4, 
            "year-end": 4, "yearend": 4
        }
        target_value = None
        if target_year:
            # Calculate the numerical value for the target date.
            target_value = (target_year * 4) + period_to_value.get(target_period, 0)

        # This is the main pagination loop. It continues until there's no "Next Page" button.
        while True:
            print(f"📄 Scraping Page {page_count}...")
            should_stop_scraping = False
            try:
                # Wait for the results container to be present before trying to extract links.
                WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, config["content_container_selector"])))
                links = self.driver.find_elements(By.CSS_SELECTOR, config["link_selector"])
            except TimeoutException:
                print(f"❌ Timed out waiting for content on page {page_count}. Halting.")
                break

            # Loop through each link found on the current page.
            for link in links:
                link_text_raw = link.text
                link_text_lower = link_text_raw.lower()
                
                # This check is not used in the current agent but could filter by keywords.
                if all(kw.lower() in link_text_lower for kw in config["search_terms"]):
                    href = link.get_attribute('href')
                    # Ensure the link is valid and we haven't already saved it.
                    if href and href not in found_reports:
                        keep_report = False
                        
                        # Use regex to find a date pattern in the link text.
                        report_year, report_period = None, None
                        match = re.search(r'(q([1-4])|h([1-2]))\s*(\d{4})', link_text_lower)
                        if match:
                            report_year = int(match.group(4))
                            report_period = match.group(1).upper()
                        
                        # Decide whether to keep the report based on the target year/period.
                        if not target_year:
                            keep_report = True
                        elif report_year and report_year == target_year:
                            if not target_period:
                                keep_report = True
                            elif report_period:
                                if report_period == target_period:
                                    keep_report = True
                                # Handle cases where target is a quarter but found is a half-year.
                                elif target_period in ["Q1", "Q2"] and report_period == "H1":
                                    keep_report = True
                                elif target_period in ["Q3", "Q4"] and report_period == "H2":
                                    keep_report = True
                        
                        if keep_report:
                            print(f"   ✅ Found matching report: {link_text_raw}")
                            found_reports[href] = link_text_raw
                            
                        # If early stopping is enabled, check the date of the current report.
                        if enable_early_stopping and target_year:
                            # Use a flexible regex to find various date formats in the title.
                            match = re.search(r'(q[1-4]|h[1-2]|year-end|ye|full-year)\s*(\d{4})', link_text_lower)
                            
                            if match:
                                report_period_raw = match.group(1)
                                report_period = report_period_raw.upper().replace('-', '')
                                report_year = int(match.group(2)) # Note: group index changed to 2

                                # Compare the numerical value of the found report to the target.
                                if target_period and target_value:
                                    found_value = (report_year * 4) + period_to_value.get(report_period, 0)
                                    if found_value < target_value:
                                        print(f"\n   -- Found report from '{report_period_raw} {report_year}', which is older than target. Stopping early. --")
                                        should_stop_scraping = True
                                        break # Stop processing links on this page.
                                elif report_year < target_year:
                                    print(f"\n   -- Found report from {report_year}, which is older than target year {target_year}. Stopping early. --")
                                    should_stop_scraping = True
                                    break

            if should_stop_scraping:
                break # Stop going to the next page.
            
            # Find and click the "Next Page" button.
            try:
                next_page_button = self.driver.find_element(By.CSS_SELECTOR, config["next_page_selector"])
                self.driver.execute_script("arguments[0].click();", next_page_button)
                page_count += 1
                print(f"   Navigating to page {page_count}...")
                time.sleep(3) # Wait for the new page to load.
            except NoSuchElementException:
                # If the button doesn't exist, we've reached the last page.
                print("\nNo 'Next Page' button found. Reached the end.")
                break
        
        return found_reports
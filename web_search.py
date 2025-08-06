import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def scrape_with_selenium(start_url):
    """
    Uses a real Chrome browser to navigate CBRE, handles iframes, correctly
    paginates through all results, and finds industrial reports.
    """
    industrial_report_links = set()
    
    # --- Setup Chrome Options ---
    chrome_options = Options()
    chrome_options.add_argument("--headless")  
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

    # --- Initialize WebDriver ---
    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("🤖 Selenium WebDriver Initialized.")

    try:
        # --- Go to the starting page ---
        driver.get(start_url)
        print(f"Navigated to: {start_url}")

        # --- Handle Cookie Consent Banner ---
        try:
            cookie_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
            )
            driver.execute_script("arguments[0].click();", cookie_button)
            print("✓ Accepted cookies using JavaScript.")
            time.sleep(2) 
        except TimeoutException:
            print("! Cookie banner not found or already accepted.")

        # --- Switch to the iFrame ---
        try:
            print("🔎 Looking for the Market Reports content iframe...")
            reports_iframe = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='search-market-results']"))
            )
            driver.switch_to.frame(reports_iframe)
            print("✓ Switched to iframe.")
            time.sleep(3)

        except TimeoutException:
            print("❌ Timed out waiting for the market reports iframe to load. Halting crawl.")
            return []

        page_count = 1
        while True:
            print(f"📄 Scraping Page {page_count}...")
            
            # --- Find Industrial Report Links ---
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "coveo-result-list-container"))
                )
                links = driver.find_elements(By.CSS_SELECTOR, ".coveo-result-list-container a")
            except TimeoutException:
                print(f"❌ Timed out waiting for the report list on page {page_count}.")
                break

            links_found_on_page = 0
            for link in links:
                if 'industrial' in link.text.lower():
                    href = link.get_attribute('href')
                    if href and href not in industrial_report_links:
                        industrial_report_links.add(href)
                        links_found_on_page += 1
            
            if links_found_on_page > 0:
                 print(f"   ✅ Found {links_found_on_page} new industrial report link(s).")
            else:
                 print(f"   No new industrial report links found on this page.")
            
            # --- FINAL PAGINATION LOGIC ---
            try:
                # Find the 'Next' button's clickable span based on the HTML provided
                next_page_button = driver.find_element(By.CSS_SELECTOR, "li.coveo-pager-next span[role='button']")
                
                print(f"   Navigating to page {page_count + 1}...")
                driver.execute_script("arguments[0].click();", next_page_button)
                page_count += 1
                time.sleep(3) # Wait for next page to load
            except NoSuchElementException:
                # This error means the 'Next' button element does not exist, so we are on the last page.
                print("\nNo 'Next Page' button found. Reached the end.")
                break 

    finally:
        driver.quit() 
        print("🤖 WebDriver closed.")
    
    return list(industrial_report_links)

# --- Main execution block ---
if __name__ == "__main__":
    cbre_reports_url = "https://www.cbre.com/insights#market-reports"
    print("-" * 50)
    print("Starting CBRE scraper with Selenium...")
    found_links = scrape_with_selenium(cbre_reports_url)
    print("-" * 50)
    
    if found_links:
        print(f"\n🎉 Success! Found a total of {len(found_links)} unique industrial reports:")
        for link in sorted(found_links):
            print(f"  - {link}")
    else:
        print("\nCould not find any links for industrial reports.")
    print("-" * 50)
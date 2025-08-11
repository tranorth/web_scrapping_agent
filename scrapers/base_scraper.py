# scapers/base_scraper.py

# Import necessary libraries
import os  # For interacting with the operating system, like creating directories


# Import the Selenium library, which automates web browser actions
from selenium import webdriver
from selenium.webdriver.common.by import By  # For selecting elements by ID, CSS Selector, etc.
from selenium.webdriver.chrome.service import Service  # For managing the ChromeDriver service
from selenium.webdriver.chrome.options import Options  # For configuring Chrome options

# A dictionary mapping string names to Selenium's 'By' classes. Not used in this version but useful for abstraction.
BY_MAP = {"ID": By.ID, "CSS_SELECTOR": By.CSS_SELECTOR, "CLASS_NAME": By.CLASS_NAME, "XPATH": By.XPATH}

class BaseScraper:
    """A reusable, intelligent web scraper class using Selenium."""

    # The __init__ method is the constructor, called when a new Scraper object is created.
    def __init__(self, headless=True):
        # Define a temporary directory for downloads relative to the current working directory.
        self.download_dir = os.path.join(os.getcwd(), "temp_downloads")
        # Create the directory if it doesn't already exist.
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
        
        # Initialize Chrome options to customize the browser's behavior.
        chrome_options = Options()
        # If headless is True, run Chrome in the background without a visible UI.
        if headless:
            chrome_options.add_argument("--headless=new")
        
        # Define browser preferences. This is crucial for handling file downloads automatically.
        prefs = {
            "download.default_directory": self.download_dir,  # Set the automatic download location.
            "download.prompt_for_download": False,  # Disable the "Save As..." dialog.
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True  # Ensure PDFs are downloaded, not viewed in-browser.
        }
        chrome_options.add_experimental_option("prefs", prefs)

        # Add common arguments for stability, especially in automated environments.
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        # Set a user-agent to mimic a real browser and avoid being blocked.
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        
        # Initialize the Chrome WebDriver with the specified service and options. This opens the browser.
        service = Service()
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        print("🤖 Selenium WebDriver Initialized.")


    def close(self):
        """Closes the WebDriver to free up system resources."""
        if self.driver:
            self.driver.quit()
            print("🤖 WebDriver closed.")
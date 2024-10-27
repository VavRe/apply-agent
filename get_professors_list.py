from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import time

def scrape_faculty_info():
    # Setup Chrome options for headless browsing
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    try:
        # Initialize the driver
        driver = webdriver.Chrome(options=chrome_options)
        
        # Get the faculty page
        print("Accessing faculty page...")
        driver.get("https://imprs.is.mpg.de/faculty/")
        
        # Wait for page to render (adjust timeout and conditions as needed)
        time.sleep(5)  # Basic wait
        
        # Get the rendered HTML content
        html_content = driver.page_source
        
        # Close the browser
        driver.quit()
        
        # Make request to the Jina API
        print("Making request to Jina API...")
        jina_url = "https://r.jina.ai/imprs.is.mpg.de/faculty/"
        response = requests.get(jina_url)
        
        if response.status_code == 200:
            # Save the results to markdown file
            print("Saving results to file...")
            with open('imprs_professors.md', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("Results saved successfully to results.md")
            return True
        else:
            print(f"Failed to get data from Jina API. Status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False


if __name__ == "__main__":
    scrape_faculty_info()
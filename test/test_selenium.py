# test_selenium.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def test_selenium():
    print("Installing ChromeDriver...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # background mode
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    
    print("Opening page...")
    driver.get("https://www.utoronto.ca/academics/undergraduate-programs")
    print(f"Page title: {driver.title}")
    print(f"Page length: {len(driver.page_source)}")
    
    driver.quit()
    print("✅ Selenium is working correctly!")

test_selenium()
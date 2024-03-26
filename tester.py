from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import time

# Specify the path to the ChromeDriver
chrome_driver_path = 'chromedriver-mac-x64/chromedriver'

# URL of the new page to interact with
url = 'https://buildspace.so/s3/demoday'
service = Service(executable_path=chrome_driver_path)
driver = webdriver.Chrome(service=service)

driver.get(url)

# Wait until the project containers are visible
WebDriverWait(driver, 10).until(
    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div[class*="framer-1wkjeqj-container"]'))
)

# Fetch the first five project containers
project_containers = driver.find_elements(By.CSS_SELECTOR, 'div[class*="framer-1wkjeqj-container"]')[:5]

for index, project in enumerate(project_containers):
    project_name = project.find_element(By.CSS_SELECTOR, 'div[class*="framer-1i5kbww"] p').text
    project_description = project.find_element(By.CSS_SELECTOR, 'div[class*="framer-1mn76q2"] p').text
    project_tag = project.find_element(By.CSS_SELECTOR, 'div[class*="framer-bxilt0"] p').text  # Extracting the tag

    # Attempt to click the play button to reveal the YouTube URL
    play_button = project.find_element(By.CSS_SELECTOR, 'button[aria-label="Play"]')
    driver.execute_script("arguments[0].click();", play_button)

    # Brief pause to ensure any animations or loading has completed
    time.sleep(2)

    # Extract the YouTube URL from the iframe src attribute
    iframe = project.find_element(By.CSS_SELECTOR, 'iframe[src*="youtube"]')
    youtube_url = iframe.get_attribute('src')

    print(f"Project {index + 1}: {project_name}")
    print(f"Description: {project_description}")
    print(f"Tag: {project_tag}")
    print(f"YouTube URL: {youtube_url}\n{'-' * 20}\n")

driver.quit()

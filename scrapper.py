from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from youtube_transcript_api import YouTubeTranscriptApi
import requests  # Import requests to make HTTP requests
import csv
import argparse
import time

parser = argparse.ArgumentParser(description='Scrape Buildspace project details.')
parser.add_argument('--s3', action='store_true', help='Scrape season 3 projects')
args = parser.parse_args()

# Configuration based on season
if args.s3:
    url = 'https://buildspace.so/s3/demoday'
    project_container_selector = 'div[class*="framer-1wkjeqj-container"]'
    tag_selector = 'div[class*="framer-bxilt0"] p'
    processed_projects_file = 'processed_projects_s3.txt'
    csv_filename = 'project_details_s3.csv'
    title_selector = 'div[class*="framer-1i5kbww"] p'
    description_selector = 'div[class*="framer-1mn76q2"] p'
else:
    url = 'https://buildspace.so/s4/demoday'
    project_container_selector = 'div[data-framer-name="Variant 5"]'
    tag_selector = 'div.framer-n0ti3h p.framer-text'
    processed_projects_file = 'processed_projects.txt'
    csv_filename = 'project_details.csv'
    title_selector = 'div[data-framer-component-type="RichTextContainer"] > p'
    description_selector = 'div[data-framer-component-type="RichTextContainer"] > p:nth-of-type(2)'


youtube_api_key = "AIzaSyAsPDvF6EOpJY-rSizXUQjljC6JolLQ3m4"

def get_youtube_video_details(video_id, api_key):
    base_video_url = 'https://www.googleapis.com/youtube/v3/videos'
    params = {
        'part': 'snippet',
        'id': video_id,
        'key': api_key
    }
    response = requests.get(base_video_url, params=params)
    if response.status_code == 200:
        data = response.json().get('items', [])[0].get('snippet', {})
        title = data.get('title', 'No title found')
        description = data.get('description', 'No description found')
        return title, description
    else:
        return 'Error fetching details', 'Error fetching details'

url = 'https://buildspace.so/s3/demoday' if args.s3 else 'https://buildspace.so/s4/demoday'
project_container_selector = 'div[class*="framer-1wkjeqj-container"]' if args.s3 else 'div[data-framer-name="Variant 5"]'
tag_selector = 'div[class*="framer-bxilt0"] p' if args.s3 else 'div.framer-n0ti3h p.framer-text'


# Specify the path to the ChromeDriver
chrome_driver_path = 'chromedriver-mac-x64/chromedriver'
service = Service(executable_path=chrome_driver_path)
driver = webdriver.Chrome(service=service)
driver.get(url)

wait_selector = project_container_selector if args.s3 else 'div[data-framer-name="Variant 5"]'
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
)
try:
    with open(processed_projects_file, 'r') as file:
        processed_projects = {line.strip() for line in file}
except FileNotFoundError:
    processed_projects = set()

# CSV setup
csv_file = open(csv_filename, 'a', newline='', encoding='utf-8')
csv_writer = csv.writer(csv_file)
# Write CSV header if file was newly created
if csv_file.tell() == 0:
    csv_writer.writerow(['Title', 'Description', 'Tag', 'YouTube URL', 'YouTube Title', 'YouTube Description', 'Transcript'])

project_containers = driver.find_elements(By.CSS_SELECTOR, project_container_selector)

for index, project in enumerate(project_containers):
    try:
        title = project.find_element(By.CSS_SELECTOR, title_selector).text
        # Use find_elements for description in s4 to use indexing, in case the first selector is used elsewhere
        description_elements = project.find_elements(By.CSS_SELECTOR, description_selector)
        description = description_elements[0].text if args.s3 else description_elements[1].text
        tag = project.find_element(By.CSS_SELECTOR, tag_selector).text

        play_button = project.find_element(By.CSS_SELECTOR, 'button[aria-label="Play"]')
        driver.execute_script("arguments[0].scrollIntoView();", play_button)
        driver.execute_script("arguments[0].click();", play_button)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'iframe[src*="youtube"]'))
        )

        iframe = project.find_element(By.CSS_SELECTOR, 'iframe[src*="youtube"]')
        youtube_url = iframe.get_attribute('src')
        
        if youtube_url in processed_projects:
            continue  # Skip already processed projects

        video_id = youtube_url.split("/embed/")[1].split("?")[0]

        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            transcript_text = ' '.join([item['text'] for item in transcript])
        except Exception as e:
            transcript_text = f"Could not fetch transcript: {e}"

        # Placeholder for YouTube video title and description retrieval
        # This part requires YouTube Data API or other methods


        youtube_title, youtube_description = get_youtube_video_details(video_id, youtube_api_key)

        csv_writer.writerow([title, description, tag, youtube_url, youtube_title, youtube_description, transcript_text])

        with open(processed_projects_file, 'a') as file:
            file.write(youtube_url + '\n')

    except Exception as e:
        print(f"Error processing Project {index + 1}: {e}")

driver.quit()
csv_file.close()

from http.client import RemoteDisconnected
import time
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException


def get_browser(headless=False, extensions=False, notifications=False, incognito=False):
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    
    if not extensions:
        chrome_options.add_argument("--disable-extensions")
    
    if not notifications:
        chrome_options.add_argument('--disable-notifications')
    
    if incognito:
        chrome_options.add_argument('--incognito')

    driver = webdriver.Chrome(executable_path='C:\\Aptana Workspace\\chromedriver.exe',
                              options=chrome_options)
    return driver


def main():
    driver = get_browser(headless=False, incognito=True)
    
    page_num = 0
    
    url_dict = {}
    while True:
        stop_loop = False
        page_url = f"https://slashdot.org/?page={page_num}"
        print(f"Processing page no. {page_num}...")
        
        try:
            driver.set_page_load_timeout(40)
            driver.get(page_url)
        except TimeoutException:
            print(f"\t{page_url} - Timed out receiving message from renderer")
            continue
        except RemoteDisconnected:
            print(f"\tError 404: {page_url} not found.")
            continue
        
        WebDriverWait(driver, timeout=40).until(EC.presence_of_element_located((By.CLASS_NAME, "paginate")))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        story_list = soup.find("div", attrs={"id": "firehoselist"}).find_all("article", attrs={"id": re.compile("firehose-")})
        
        for story in story_list:
            title_tag = story.find("span", attrs={"class": "story-title"})
            if not title_tag:
                continue

            title_id = title_tag['id'].replace("title-", "")
            story_url = title_tag.find("a")['href']
            url_dict[title_id] = f"https:{story_url}"
            
            time_tag = story.find("time", attrs={"id": f"fhtime-{title_id}"})
            date_obj = datetime.strptime(time_tag['datetime'], "on %A %B %d, %Y @%I:%M%p").strftime("%Y-%m-%d")
            print(f"\t{date_obj}")
            
            if date_obj < '2019-12-01':
                stop_loop = True
                break
        
        if stop_loop:
            break
            
        
        page_num += 1
        time.sleep(7)
    
    driver.quit()
    print("Writing {} key-value pairs to json file...")
    with open("slashdot_urls.json", 'w') as outfile:
        json.dump(url_dict, outfile, indent=4)

    print("DONE!!!")


if __name__ == "__main__":
    main()
from http.client import RemoteDisconnected
import time
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import psycopg2


HOST = "localhost"
DATABASE = "coronavirus"
USER = "postgres"
PASSWORD = "cavin"


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
    conn = psycopg2.connect(host=HOST, database=DATABASE, user=USER, password=PASSWORD)
    cur = conn.cursor()

    print("Reading slashdot url's...")
    with open('slashdot_urls.json', 'r') as file:
        all_urls = json.load(file)

    driver = get_browser(headless=False, incognito=True)

    clean_text = lambda txt: re.sub(r'\s+', ' ', " ".join(txt.strip().splitlines()))
    kwd_match = lambda kwd: re.compile(f"{'|'.join(kwd)}", flags=re.IGNORECASE).search
    
    keywords = ['covid', 'coronavirus', 'wuhan', 'ncov']
    
    if not keywords:
        filtered_url = all_urls.copy()
    else:
        filtered_url = {k:v for k, v in all_urls.items() if kwd_match(keywords)(v)}
    
    length_of_url = len(filtered_url.keys())

    for idx, (title_id, page_url) in enumerate(filtered_url.items()):
        print(f"Processing url {idx+1} of {length_of_url}...\n\t{page_url}")

        try:
            driver.set_page_load_timeout(40)
            driver.get(page_url)
        except TimeoutException:
            print(f"\t{page_url} - Timed out receiving message from renderer")
            continue
        except RemoteDisconnected:
            print(f"\tError 404: {page_url} not found.")
            continue
        
        WebDriverWait(driver, timeout=40).until(EC.presence_of_element_located((By.ID, "fhft")))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        story_list = soup.find("span", attrs={"class": "story-title"})
        title = story_list.find("a").text.strip()
        
        body_tag = soup.find("div", attrs={"id": f"fhbody-{title_id}"})
        body_text = clean_text(body_tag.text) if body_tag else None
        
        story_tags = soup.find("div", attrs={"class": "story-tags"})
        if story_tags:
            tags = ', '.join(clean_text(story_tags.text).split(' '))
        else:
            tags = None
        
        time_tag = soup.find("time", attrs={"id": f"fhtime-{title_id}"})
        timestamp_obj = datetime.strptime(time_tag['datetime'], "on %A %B %d, %Y @%I:%M%p")
        
        posted_by_tag = soup.find("span", attrs={"class": "story-byline"})
        posted_by = clean_text(posted_by_tag.text).split('on')[0].replace("Posted by ", "").strip()
        
        query = """
                INSERT INTO story(id, url, title, article, tags, posted_by, added_time)
                SELECT sub_query.* FROM
                (SELECT %s  AS id, %s, %s, %s, %s, %s, %s) sub_query
                LEFT JOIN story s ON sub_query.id = s.id
                WHERE s.id IS NULL;
                """
 
        data = (title_id, page_url, title, body_text, tags, posted_by, timestamp_obj)
        cur.execute(query, data)
        
        while True:
            loaded_comms = soup.find("span", attrs={"class": "loadedcommentcnt"})
            total_comms = soup.find("span", attrs={"class": "totalcommentcnt"})
            if loaded_comms.text == total_comms.text:
                break
            driver.find_element_by_id("more_comments_button").click()
            soup = BeautifulSoup(driver.page_source, "html.parser")
            time.sleep(2)

        move = ActionChains(driver)
        en =  driver.find_element_by_id("ccw-abbr-bar-pos").find_element_by_class_name("ccwb")
        move.click_and_hold(en).move_by_offset(400, 0).release().perform()
        en =  driver.find_element_by_id("ccw-abbr-bar-pos").find_element_by_class_name("ccwa")
        move.click_and_hold(en).move_by_offset(400, 0).release().perform()
        time.sleep(1)
          
        comments = soup.find("ul", attrs={"id": "commentlisting"}).find_all("div", 
                                                                            attrs={"id": re.compile("comment_\d+")})
        for idx, comment in enumerate(comments):
            comment_body = comment.find("div", attrs={"id": re.compile("comment_body_\d+")})
            score_tag = comment.find("span", attrs={"class": "score"})
            span_tag = comment.find("span", attrs={"class": "otherdetails"})
            
            insightful, informative, interesting, funny = [0, 0, 0, 0]

            if comment_body:
                comment_id = span_tag['id'].replace("comment_otherdetails_", "")
                commented_by_tag = comment.find("span", attrs={"class": "by"})
                a_tag = commented_by_tag.find("a")
                if a_tag:
                    commented_by = a_tag.text.strip()
                else:
                    commented_by = commented_by_tag.text.replace("by", "").strip()
                
                comm_text = clean_text(comment_body.text)
                comm_feature = score_tag.text.strip()
                score = int(re.findall(r'\d+', comm_feature)[0])
                
                if 'insightful' in comm_feature.lower():
                    insightful = 1
                
                if 'informative' in comm_feature.lower():
                    informative = 1
                
                if 'interesting' in comm_feature.lower():
                    interesting = 1
                
                if 'funny' in comm_feature.lower():
                    funny = 1
                
                query = """
                        INSERT INTO comments(id, story_id, comment, commented_by, score, insightful, informative,
                        interesting, funny)
                        SELECT sub_query.* FROM
                        (SELECT %s  AS id, %s, %s, %s, %s, %s, %s, %s, %s) sub_query
                        LEFT JOIN comments c ON sub_query.id = c.id
                        WHERE c.id IS NULL;
                        """
                        
                data = (comment_id, title_id, comm_text, commented_by, score, insightful, informative,
                        interesting, funny)
                cur.execute(query, data)

        time.sleep(3)
    
    driver.quit()
    conn.commit()
    cur.close()
    conn.close()
    
    print("DONE!!!")


if __name__ == "__main__":
    main()
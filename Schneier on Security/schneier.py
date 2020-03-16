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
import psycopg2


HOST = "localhost"
DATABASE = "schneier"
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
    driver = get_browser(headless=False, incognito=True)
    
    page_url = "https://www.schneier.com/"
    idx = 1

    while True:
        print(f"Processing page no. {idx}...")
        
        try:
            driver.set_page_load_timeout(200)
            driver.get(page_url)
        except TimeoutException:
            print(f"\t{page_url} - Timed out receiving message from renderer")
            continue
        except RemoteDisconnected:
            print(f"\tError 404: {page_url} not found.")
            continue
        
        WebDriverWait(driver, timeout=40).until(EC.presence_of_element_located((By.CLASS_NAME, "stepthrough")))
        soup = BeautifulSoup(driver.page_source, "html.parser")

        ealier_entry = soup.find("div", attrs={"class": "stepthrough"}).find("a", attrs={"class": "earlier"})
        
        if not ealier_entry:
            break

        articles = soup.find("div", attrs={"id": "content"}).find_all("article")

        for article in articles:
            h2_tag = article.find("h2", attrs={"class": "entry"})
            id = h2_tag['id']

            a_tag = h2_tag.find("a")
            url = a_tag['href'] if a_tag else None
            title = a_tag.text.strip() if a_tag else None
            
            body_tags = article.find_all(re.compile("[p|strong|i|ul]"), attrs={"class": None, "id": None, "type": None})
            body = " ".join([k.text.strip() for k in body_tags])
            
            entry_tag = article.find("p", attrs={"class": "entry-tags"})
            tag_arr = [k.text for k in entry_tag.find_all("a")] if entry_tag else [""]
            tags = ', '.join(tag_arr)
            
            posted_tag = article.find("p", attrs={"class": "posted"})
            date_obj = None
            if posted_tag:
                datetime_tag = posted_tag.find("a").text.strip()
                date_obj = datetime.strptime(datetime_tag, "Posted on %B %d, %Y at %I:%M %p")
                
            query = """
                    INSERT INTO article(id, url, title, body, tags, posted_datetime)
                    SELECT sub_query.* FROM
                    (SELECT %s  AS id, %s, %s, %s, %s, %s) sub_query
                    LEFT JOIN article a ON sub_query.id = a.id
                    WHERE a.id IS NULL;
                    """
 
            data = (id, url, title, body, tags, date_obj)
            cur.execute(query, data)
            
            comment_arr = [k['href'] for k in posted_tag.find_all("a")]
            if len(comment_arr) != 2:
                print(f"\tNo comments found for this article - {url}")
                continue

            print("\tProcessing comments...")
            comment_url = comment_arr[1]

            try:
                driver.set_page_load_timeout(200)
                driver.get(comment_url)
            except TimeoutException:
                print(f"\t{comment_url} - Timed out receiving message from renderer")
                continue
            except RemoteDisconnected:
                print(f"\tError 404: {comment_url} not found.")
                continue
            
            WebDriverWait(driver, timeout=40).until(EC.presence_of_element_located((By.CLASS_NAME, "subscribe-comments")))
            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            comment_tags = soup.find_all("article")[1:]
            
            for comment in comment_tags:
                cid = comment.find("div", attrs={"class": re.compile("comment by-")})['id']
                
                comment_credit = comment.find("p", attrs={"class": "commentcredit"})
                commented_by = comment_credit.find("span").text.strip()
                
                comment_body_tags = comment.find_all(re.compile("[p|strong|i|ul]"), attrs={"class": None, "id": None, "type": None})
                comment_body = " ".join([k.text.strip() for k in comment_body_tags])
                
                posted_tag = comment_credit.find_all("a")[-1]
                date_obj = None
                if posted_tag:
                    datetime_tag = posted_tag.text.strip()
                    try:
                        date_obj = datetime.strptime(datetime_tag, "%B %d, %Y %I:%M %p")
                    except:
                        print(datetime_tag)

                query = """
                        INSERT INTO comments(id, article_id, comment, commented_by, posted_datetime)
                        SELECT sub_query.* FROM
                        (SELECT %s  AS id, %s, %s, %s, %s) sub_query
                        LEFT JOIN comments c ON sub_query.id = c.id
                        WHERE c.id IS NULL;
                        """

                data = (cid, id, comment_body, commented_by, date_obj)
                cur.execute(query, data)

        page_url = ealier_entry['href']
        idx += 1
        time.sleep(3)
    
    driver.quit()
    conn.commit()
    cur.close()
    conn.close()

    print("DONE!!!")


if __name__ == "__main__":
    main()
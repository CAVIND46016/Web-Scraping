"""
Cellarbrations
https://www.cellarbrations.com.au/store-locator
"""

import urllib.request as urllib2
from bs4 import BeautifulSoup
import selenium
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from geopy.geocoders import GoogleV3 as g3
import http
import time
import pandas as pd
import json

web_url = "https://www.cellarbrations.com.au/store-locator"

BROWSER = webdriver.Firefox()

aus_postal_codes_df = pd.read_csv("au_postal_codes.csv")
aus_postal_codes_df = aus_postal_codes_df.loc[~aus_postal_codes_df['Postal Code'].isnull()]
all_codes = aus_postal_codes_df['Postal Code'].unique().tolist()

l = len(all_codes)

d = {}
for idx in range(l):
    print(f"Processing zip_code: {idx+1}/{l}")
    try:
        BROWSER.set_page_load_timeout(200)
        BROWSER.get(web_url)
    except http.client.RemoteDisconnected:
        raise Exception(f"Error 404: {web_url} not found.")
    
    try:
        WebDriverWait(BROWSER, 10).until(EC.presence_of_element_located\
                                            ((By.CLASS_NAME, "panel-panel-inner")))
    except selenium.common.exceptions.TimeoutException:
        raise Exception(f"Error 404: {web_url} not found.")

    post_code = BROWSER.find_element_by_id("edit-location")
    zip_code = str(int(all_codes[idx]))
    post_code.send_keys(zip_code)

    BROWSER.find_element_by_id("edit-submit").click()
    
    soup = BeautifulSoup(BROWSER.page_source, "html.parser")
    
    item_list = soup.find("div", attrs={"class": "item-list"})
    if not item_list:
        continue

    items = item_list.find_all("span", attrs={"class": "field-content"})
    
    for item in items:
        a_tag = item.find("a")
        if not a_tag:
            continue
        
        title = a_tag.text.strip()
        try:
            d[title] = a_tag["href"]
        except KeyError:
            continue
            
    time.sleep(1)

BROWSER.quit()
print(json.dumps(d, indent=4))    
with open('cellarbrations_locs.json', 'w') as outfile:
    json.dump(d, outfile, indent=4)
        
print("done")


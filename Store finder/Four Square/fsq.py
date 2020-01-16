"""
Four Square
https://www.foursquare.co.nz/
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

web_url = "https://www.foursquare.co.nz/"

BROWSER = webdriver.Firefox()

try:
    BROWSER.set_page_load_timeout(200)
    BROWSER.get(web_url)
except http.client.RemoteDisconnected:
    raise Exception(f"Error 404: {web_url} not found.")

try:
    WebDriverWait(BROWSER, 10).until(EC.presence_of_element_located\
                                        ((By.ID, "stores-nav")))
except selenium.common.exceptions.TimeoutException:
    raise Exception(f"Error 404: {web_url} not found.")

BROWSER.find_element_by_partial_link_text("Choose Your Store").click()

clickable_regions = BROWSER.find_elements_by_class_name("regionSelect")
region = {}

for r in clickable_regions:
    r.click()
    time.sleep(1)
    soup = BeautifulSoup(BROWSER.page_source, "html.parser")
    items = soup.find("div", attrs={"id": "storeListing"}).find_all("li")
     
    for item in items:
        a_tag = item.find("a")
        if not a_tag:
            continue
        region[a_tag.text.strip()] = a_tag['href']
     
    time.sleep(2)
    
BROWSER.quit()


lat_long_switch = 0
key = 'AIzaSyDhx8Gb9-CPLfCN2KBo1_swmuCQgeDbwwc'

g = g3(api_key=key)

cnt = 1
store_num = []
store_name = []
address = []
lat, long = [], []

BROWSER = webdriver.Firefox()

for _, val in region.items():
    url = f"{web_url}{val}"
    print(url)
    store_num.append(cnt)
    
    s_name = f"Four Square {val.split('=')[1]}"
    store_name.append(s_name)
    
    try:
        BROWSER.set_page_load_timeout(200)
        BROWSER.get(url)
    except http.client.RemoteDisconnected:
        print(f"Error 404: {url} not found.")
        continue
    
    soup = BeautifulSoup(BROWSER.page_source, "html.parser")
    div_id = soup.find("div", attrs={"id": "myLocal"})
    addr = div_id.find("td", class_=None).text.strip()
    address.append(addr)
    
    if lat_long_switch:
        location = g.geocode(addr, timeout=10)
        if not location:
            lat.append(None)
            long.append(None)
            continue
        
        lat.append(location.latitude)
        long.append(location.longitude)
    else:
        lat.append(None)
        long.append(None)

    print(f"\t{cnt} - {s_name}: {addr} | ({lat[-1]}, {long[-1]})")
    cnt += 1
    time.sleep(1)

BROWSER.quit()
df = pd.DataFrame({"store_num": store_num,
                   "store_name": store_name,
                   "address": address,
                   "latitude": lat,
                   "longitude": long})

df["country"] = "New Zealand"
df["country_code"] = "NZ"

df.to_csv("four_square_stores.csv", index=False)
print("done")


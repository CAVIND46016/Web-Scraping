"""
Cellarbrations
https://www.cellarbrations.com.au/store-locator
"""

import urllib.request as urllib2
from bs4 import BeautifulSoup
import json

from geopy.geocoders import GoogleV3 as g3
import http
import time
import pandas as pd

web_url = "https://www.cellarbrations.com.au"

request_header = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
                  (KHTML, like Gecko) Chrome/64.0.3282.186 Safari/537.36"}

with open('cellarbrations_locs.json', 'r') as f:
    locs = json.load(f)

relevant_locs = {k: v for k, v in locs.items() if 'Cellarbrations' in k}

lat_long_switch = 0
key = 'AIzaSyDhx8Gb9-CPLfCN2KBo1_swmuCQgeDbwwc'

g = g3(api_key=key)

cnt = 1
store_num = []
store_name = []
address = []
lat, long = [], []

for key, val in relevant_locs.items():
    url = f"{web_url}{val}"
    print(url)

    try:
        req = urllib2.Request(url, headers=request_header)
        page = urllib2.urlopen(req, timeout=200).read()
    except http.client.RemoteDisconnected:
        print(f"Error 404: {url} not found.")
        continue

    soup = BeautifulSoup(page, "html.parser")

    div_class = soup.find("div", attrs={"class": "panel-panel-inner"})

    store_num.append(cnt)
    s_name = key
    store_name.append(s_name)

    addr_tag = div_class.find("div", attrs={"property": "schema:servicePostalAddress"})
    addr = addr_tag.find("div", attrs={"class": "street-block"}).text.strip() + " " + \
           addr_tag.find("span", attrs={"class": "locality"}).text.strip() + \
           " " + addr_tag.find("span", attrs={"class": "state"}).text.strip() + \
           " " + addr_tag.find("span", attrs={"class": "postal-code"}).text.strip()
    address.append(addr)

    if lat_long_switch:
        location = g.geocode(addr, timeout=40)
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

df = pd.DataFrame({"store_num": store_num,
                   "store_name": store_name,
                   "address": address,
                   "latitude": lat,
                   "longitude": long})

df["country"] = "Australia"
df["country_code"] = "AU"

df.to_csv("cellarbrations_stores.csv", index=False)
print("done")

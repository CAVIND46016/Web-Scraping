"""
New World
https://www.newworld.co.nz/

Steps:
1) go to: https://www.newworld.co.nz/upper-north-island/bay-of-plenty/opotiki
2) click change store
3) right click and inspect the first `store_details` tab.
4) find  the div class "m-storeselector" in the html inspect page, right click and select COPY OUTER HTML
5) save this copied content to a static html file to extract data from.
"""


from bs4 import BeautifulSoup
from geopy.geocoders import GoogleV3 as g3
import pandas as pd


lat_long_switch = 0
key = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

g = g3(api_key=key)

cnt = 1
store_num = []
store_name = []
address = []
lat, long = [], []

with open("new_world_html.html", encoding="utf-8") as f:
    data = f.read()
    soup = BeautifulSoup(data, 'html.parser')
    
    div_classes = soup.find_all("div", attrs={"class": "m-storesearch__card"})
    
    for div in div_classes:
        store_num.append(cnt)
        
        s_name = div.find("div", attrs={"class": "m-storesearch__card-header"}).text.strip()
        store_name.append(s_name)
        
        addr = div.find("div", attrs={"class": "m-storesearch__card-text"}).text.strip()
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

    
df = pd.DataFrame({"store_num": store_num,
                   "store_name": store_name,
                   "address": address,
                   "latitude": lat,
                   "longitude": long})

df["country"] = "New Zealand"
df["country_code"] = "NZ"

df.to_csv("new_world_stores.csv", index=False)
print("done")
        

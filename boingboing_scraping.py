"""
BoingBoing web scraping.
"""
import urllib.request as urllib2
from datetime import datetime
import http
import sys
import time
import re

from bs4 import BeautifulSoup
from selenium import webdriver

from util import connectToDatabaseServer
from boingboing_comments import fetch_comment_info

# system default value is 1000; to avoid recursion depth to exceed,
sys.setrecursionlimit(10000)

# BoingBoing - A directory of mostly wonderful things
BB_URL = "https://boingboing.net/grid/"

# PostgreSQL Database name
# DATABASE = "BoingBoing"
DATABASE = "new_bb_2015_18"

# Recursion breakpoint definition
START_CUTOFF_DATE = datetime.strptime("3/17/2018", "%m/%d/%Y").date()
END_CUTOFF_DATE = datetime.now().date()

if START_CUTOFF_DATE > END_CUTOFF_DATE:
    raise ValueError('Cutoff start date is greater than end date.')

if END_CUTOFF_DATE > datetime.now().date():
    raise ValueError('Cutoff end date is greater than current date.')

# posts filter
REQUIRED_TAGS = []#['facebook', 'social media']

# Fixing the 'IncompleteRead' bug using http
# https://stackoverflow.com/questions/14149100/incompleteread-using-httplib
http.client.HTTPConnection._http_vsn = 10
http.client.HTTPConnection._http_vsn_str = 'HTTP/1.0'

# firefox browser object
BROWSER = webdriver.Firefox()

def extract_post_story(div_id_story):
    """
    Extracts the post text contents, strips line breaks and whitespaces.
    """
    
    before_keyword = "SHARE /"
    post_story = div_id_story.get_text().strip().replace('\n', ' ').replace('\r', '')
        
    return post_story[:post_story.find(before_keyword)]

def scrape(web_url, conn, cur, i, pg_no):
    """
    Scrapes the 'web_url' and inserts values to postgresql table.
    """
    
    # Added timeout for the error: http.client.RemoteDisconnected: 
    # Remote end closed connection without response.
    try:
        page = urllib2.urlopen(web_url, timeout=200)
    except http.client.RemoteDisconnected:
        print("Error 404: {} not found.".format(web_url))
        return 0
    
    soup = BeautifulSoup(page, "html.parser")
    div_id_posts = soup.find("div", attrs={"id":"posts"})
    div_class_feature = div_id_posts.find_all("div", attrs={"class":"feature"})
    
    # If no features found on the page, return
    if len(div_class_feature) == 0:
        return 0
    
    #**************************************ARTICLES**************************************
    for feature in div_class_feature:
        a_class_headline = feature.find("a", attrs={"class":"headline"})  
        try:
            post_page = urllib2.urlopen(a_class_headline['href'], timeout=200)
        except http.client.RemoteDisconnected:
            print("Error 404: {} not found.".format(a_class_headline['href']))
            continue
            
        post_soup = BeautifulSoup(post_page, "html.parser")
        
        div_class_share = post_soup.find("div", attrs={"class":"share"})
        # if no comments on the article, skip article
        if not div_class_share:
            continue
        
        try:
            date_str = re.findall(r"\d+/\d+/\d+", a_class_headline['href'])[0]
            posteddate = datetime.strptime(date_str, "%Y/%m/%d").date()
        except ValueError:
            posteddate = None
            print("Date format error.")
            
        # apply the date filter
        if posteddate < START_CUTOFF_DATE or posteddate > END_CUTOFF_DATE:
            return 0
        
        article_headline = a_class_headline.text.strip()
        
        div_id_story = post_soup.find("div", attrs={"id":"story"})
        if not div_id_story:
            div_id_story = post_soup.find("article", attrs={"id":"text"})
            if not div_id_story:
                div_id_story = post_soup.find("div", attrs={"id":"container"})
                
        post_txt = extract_post_story(div_id_story)

        h3_class_thetags = div_class_share.find("h3", attrs={"class":"thetags"})
        if not h3_class_thetags:
            post_tags = ""
        else:
            post_tags = ', '.join([x.lower() for x in [tag.string.strip().replace('/', '') \
                                                       for tag in h3_class_thetags] if x != ''])
        
        div_class_navbyline = post_soup.find("div", attrs={"class":"navbyline"})
        if not div_class_navbyline:
            div_class_navbyline = post_soup.find("header", attrs={"id":"bbheader"})
        
        span_class_author = div_class_navbyline.find("span", attrs={"class":"author"})

        # Apply the 'REQUIRED_TAGS' filter
        is_ok = False
        if REQUIRED_TAGS:
            for elem in REQUIRED_TAGS:
                if elem in post_tags or elem in article_headline.lower():
                    is_ok = True
                    break
        else:
            is_ok = True      
            
        if not is_ok:
            continue
        
        query = "INSERT INTO posts(postno, a_page_url, headline, text, tags, author, posteddate) \
                    VALUES (%s, %s, %s, %s, %s, %s, %s);"
        data = (i, 
                a_class_headline['href'],
                article_headline, 
                post_txt, 
                post_tags, 
                [x.string for x in span_class_author.find("a")][0],
                posteddate)
                
        cur.execute(query, data)
        print("FOUND POST: {}, {}".format(i, article_headline))
        
        #**************************************COMMENTS**************************************
        a_class_bbs = div_class_share.find("a", attrs={"class":"bbs"}) 
        comments = fetch_comment_info(BROWSER, a_class_bbs['href'], i, cur)
        
        for _, value in comments.items():
            if value['comm_text'] != "":
                cquery = "INSERT INTO comments(commentno, postno, \
                comments, postedby, likes, posteddate) VALUES (%s, %s, %s, %s, %s, %s);"
                cdata = (value['comm_no'], i, value['comm_text'], \
                         value['postedby'], value['likes'], value['date'])
                cur.execute(cquery, cdata)
        i += 1
 
    # Construct next page url.
    print("Page no: {} - {}".format(pg_no, posteddate))
    pg_no += 1
    next_page_url = BB_URL + "page/{}/".format(pg_no)

    # recursive logic
    scrape(next_page_url, conn, cur, i, pg_no)

def main():
    """
    Entry-point for the function.
    """
    start_time = time.time()
    conn_obj = connectToDatabaseServer(DATABASE)
    
    if conn_obj == -1:
        print("Connection to PostgreSQL Database: {} failed.".format(DATABASE))
        sys.exit(0)
    else:
        conn = conn_obj[0]
        cur = conn_obj[1]
  
    scrape(BB_URL, conn, cur, i=1, pg_no=1)
    
    conn.commit()
    cur.close()
    conn.close()
    
    print("Webdata scraped successfully in {} seconds.".format(time.time()-start_time))
    
if __name__ == "__main__":
    main()
    

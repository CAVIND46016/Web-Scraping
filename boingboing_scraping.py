import urllib.request as urllib2
from bs4 import BeautifulSoup
from selenium import webdriver
from util import connectToDatabaseServer
from boingboing_comments import fetch_comment_info
from datetime import datetime
import http
import sys
import time
import re

# system default value is 1000; to avoid recursion depth to exceed,
sys.setrecursionlimit(10000)

# BoingBoing - A directory of mostly wonderful things
bb_url = "https://boingboing.net/grid/";

# PostgreSQL Database name
DATABASE = "BoingBoing";

# Recursion breakpoint definition
start_cutoffdate = datetime.strptime("1/1/2012", "%m/%d/%Y").date()
# end_cutoffdate   = datetime.strptime("12/31/2016", "%m/%d/%Y").date()
end_cutoffdate   = datetime.now().date()

if(start_cutoffdate > end_cutoffdate):
    raise ValueError('Cutoff start date is greater than end date')

if(end_cutoffdate > datetime.now().date()):
    raise ValueError('Cutoff end date is greater than current date')

# posts filter
required_tags = ['facebook', 'social media']

# Fixing the 'IncompleteRead' bug using http
# https://stackoverflow.com/questions/14149100/incompleteread-using-httplib
http.client.HTTPConnection._http_vsn = 10
http.client.HTTPConnection._http_vsn_str = 'HTTP/1.0'

# firefox browser object
browser = webdriver.Firefox()

def extract_post_story(div_id_story):
    before_keyword = "SHARE /"
    post_story = div_id_story.get_text().strip().replace('\n', ' ').replace('\r', '')
        
    return post_story[:post_story.find(before_keyword)]

def scrape(web_url, conn, cur, i, pg_no):
    # Added timeout for the error: http.client.RemoteDisconnected: Remote end closed connection without response
    http.client.HTTPConnection(host = web_url, port = 80, timeout=200)
    page = urllib2.urlopen(web_url)
        
    soup = BeautifulSoup(page, "html.parser")

    div_id_posts = soup.find("div", attrs={"id":"posts"})
    
    div_class_feature = div_id_posts.find_all("div", attrs={"class":"feature"})
    
    """ **************************************ARTICLES************************************** """
    for feature in div_class_feature:
        a_class_headline = feature.find("a", attrs={"class":"headline"})  
        post_page = urllib2.urlopen(a_class_headline['href'])
        post_soup = BeautifulSoup(post_page, "html.parser")
        
        # if no comments on the article, skip article
        div_class_share = post_soup.find("div", attrs={"class":"share"})
        
        try:
            date_str = re.findall("\d+/\d+/\d+", a_class_headline['href'])[0]
            posteddate = datetime.strptime(date_str, "%Y/%m/%d").date()
        except:
            posteddate = None;
            print("Date format error.")
            
        # apply the date filter
        if(posteddate < start_cutoffdate or start_cutoffdate > end_cutoffdate):
            return 0;
            
        if(not div_class_share):
            continue;
        
        article_headline = a_class_headline.text.strip()
        
        div_id_story = post_soup.find("div", attrs={"id":"story"})
        if(not div_id_story):
            div_id_story = post_soup.find("article", attrs={"id":"text"})
            if(not div_id_story):
                div_id_story = post_soup.find("div", attrs={"id":"container"})
                
        post_txt = extract_post_story(div_id_story)

        h3_class_thetags = div_class_share.find("h3", attrs={"class":"thetags"})
        if(not h3_class_thetags):
            post_tags = "";
        else:
            post_tags = ', '.join([x.lower() for x in [tag.string.strip().replace('/', '') for tag in h3_class_thetags] if x != ''])
        
        div_class_navbyline = post_soup.find("div", attrs={"class":"navbyline"})
        if(not div_class_navbyline):
            div_class_navbyline = post_soup.find("header", attrs={"id":"bbheader"})
        
        span_class_author = div_class_navbyline.find("span", attrs={"class":"author"})
        
        span_id_metadata = div_class_navbyline.find("span", attrs={"id":"metadata"})
        if(not span_id_metadata):
            span_id_metadata = div_class_navbyline.find("span", attrs={"class":"time"})

        # apply the 'tags' filter
        is_OK = False;
        if(required_tags):
            for elem in required_tags:
                if(elem in post_tags or elem in article_headline.lower()):
                    is_OK = True;
                    break;
        else:
            is_OK = True      
            
        if(not is_OK):
            continue;
        
        query =  "INSERT INTO posts(postno, a_page_url, headline, text, tags, author, posteddate) VALUES (%s, %s, %s, %s, %s, %s, %s);"
        data = (i, 
                a_class_headline['href'],
                article_headline, 
                post_txt, 
                post_tags, 
                [x.string for x in span_class_author.find("a")][0],
                posteddate);
                
        cur.execute(query, data);
        print("FOUND POST: {}, {}".format(i, article_headline))
        
        """ **************************************COMMENTS************************************** """
        a_class_bbs = div_class_share.find("a", attrs={"class":"bbs"}) 
        comments = fetch_comment_info(browser, a_class_bbs['href'], i, cur)
        
        for _, value in comments.items():
            if(value['comm_text'] != ""):
                cquery =  "INSERT INTO comments(commentno, postno, comments, postedby, likes, posteddate) VALUES (%s, %s, %s, %s, %s, %s);"
                cdata = (value['comm_no'], i, value['comm_text'], value['postedby'], value['likes'], value['date']);
                cur.execute(cquery, cdata);
        i += 1
 
    # construct next page url.
    next_page_url = bb_url + "page/{}/".format(pg_no + 1)
    print("Page no: {} - {}".format(pg_no, posteddate))
    pg_no += 1
    
    if(not next_page_url):
        print("URL does not exist: {}".format(next_page_url))
        return 0;

    scrape(next_page_url, conn, cur, i, pg_no)

def main():
    s = time.time()
    
    conn_obj = connectToDatabaseServer(DATABASE);
    
    if(conn_obj == -1):
        print_text = "Connection to PostgreSQL Database: {} failed.".format(DATABASE);
        print(print_text);
        sys.exit(0);
    else:
        conn = conn_obj[0];
        cur = conn_obj[1];
  
    scrape(bb_url, conn, cur, i = 432, pg_no = 2989);  
    
    conn.commit()
    cur.close()
    conn.close()
    
    print_text = "Webdata scraped successfully in {} seconds.".format(time.time()-s)
    print(print_text)
    
if(__name__ == "__main__"):
    main()

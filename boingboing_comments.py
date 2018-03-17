"""
https://stackoverflow.com/questions/41706274/beautifulsoup-returns-incomplete-html
The page setup is such that, by default, 
approx. 19 <div class="topic-post clearfix regular"></div> tags on boingboing comments are
loaded at startup and the remaining get loaded once the page is manually scrolled down. 
We use selenium web-driver to achieve the manual scrolling.
We need either the geckodriver(https://github.com/mozilla/geckodriver/releases) for firefox 
or the chromedriver (latest release 2.3.6 --> 
https://chromedriver.storage.googleapis.com/index.html?path=2.36/)
Note: the executable driver file must be in the same directory as the .py file.
"""
from datetime import datetime
import http
import re
import time
import math

from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

SCREEN_HEIGHT_IN_PIXELS = 1080
COMMENTS_SCREEN_SIZE = 3
SCROLL_WAIT_TIME = 1

# Fixing the 'IncompleteRead' bug using http
# https://stackoverflow.com/questions/14149100/incompleteread-using-httplib
http.client.HTTPConnection._http_vsn = 10
http.client.HTTPConnection._http_vsn_str = 'HTTP/1.0'

def fetch_comment_info(browser, url, postno, cur, delay=100):
    """
    Fetches user comments in 'url'.
    """
    
    comments = {}
    # indicates presence of div_class_share but no a_class_bbs
    try:
        # Added timeout for the error: http.client.RemoteDisconnected: 
        # Remote end closed connection without response
        browser.set_page_load_timeout(200)
        browser.get(url)
    except http.client.RemoteDisconnected:
        return comments
        
    WebDriverWait(browser, delay).until(EC.presence_of_element_located\
                                        ((By.CLASS_NAME, "container")))

    soup = BeautifulSoup(browser.page_source, "html.parser")
    
    # Replies, Views, Users, Likes and Links
    num = 0
    topic_str = ["replies", "view", "user", "like", "link"]
    topic_map = [0] * len(topic_str)
    
    div_class_topicmap = soup.find("div", attrs={"class":"topic-map"})
    if div_class_topicmap:
        li_all = div_class_topicmap.find_all("li")
        for li_tag in li_all:
            li_text = li_tag.text.strip()
            span_class_number = li_tag.find("span")
            str_found = False
            for i in topic_str:
                if i in li_text:
                    str_found = True
                    break
                
            if str_found and span_class_number:
                if "k" in span_class_number.text:
                    if "." in span_class_number.text:
                        tmp = re.findall(r"\d+\.\d+", span_class_number.text)[0]
                    else:
                        tmp = re.findall(r"\d+", span_class_number.text)[0]
                        
                    num = int(float(tmp) * 1000)
                else:
                    num = int(span_class_number.text)
                
                for i, _ in enumerate(topic_str):
                    if topic_str[i] in li_text:
                        topic_map[i] = num
                    
    # Replies, Views, Users, Likes and Links
    
    tmp = 0            
    query = "UPDATE posts SET c_page_url = %s, replies = %s, views = %s, \
                users = %s, likes = %s, links = %s WHERE postno = %s;"
    if topic_map[0] >= 1:
        tmp = topic_map[0] - 1
    data = (url, tmp, topic_map[1], topic_map[2], topic_map[3], topic_map[4], postno)
        
    cur.execute(query, data)
    
    scrolls = math.ceil(topic_map[0]/COMMENTS_SCREEN_SIZE)

    for i in range(scrolls):
        soup = BeautifulSoup(browser.page_source, "html.parser")
        div_class_comment = soup.find_all("div", \
                                          attrs={"class":\
                                                 "topic-post clearfix regular"}) + \
                            soup.find_all("div", \
                                          attrs={"class":\
                                                 "topic-post clearfix topic-owner \
                                                 group-editors regular"})
                                
        comm_no = 1
        for dc_comment in div_class_comment:
            div_class_user_card = dc_comment.find("div", \
                                                  attrs={"class":"names trigger-user-card"})
            postedby = None
            if div_class_user_card:
                span_class_firstusername = dc_comment.find("span")
                if span_class_firstusername:
                    postedby = span_class_firstusername.find("a").text
                    
                    post_date = dc_comment.find("div", attrs={"class":"post-info post-date"})
                    a_class_post_date = post_date.find("a", attrs={"class":"post-date"})
                    posteddate = a_class_post_date.find("span")['title']
                    div_class_cooked = dc_comment.find("div", attrs={"class":"cooked"})
                    comm_text = div_class_cooked.text.strip().replace('\n', '').replace('\r', '')
                    
                    dict_primary_key = postedby + ' ' + posteddate + ' ' + comm_text
                    
                    if dict_primary_key not in comments:
                        comments[dict_primary_key] = {}
                        comments[dict_primary_key]['postedby'] = postedby
                        comments[dict_primary_key]['date'] = datetime.strptime\
                        (posteddate, "%b %d, %Y %I:%M %p").date()
                        
                        comments[dict_primary_key]['comm_no'] = comm_no
                        
                        div_class_cooked = dc_comment.find("div", attrs={"class":"cooked"})
                        comments[dict_primary_key]['comm_text'] = comm_text
                        
                        div_class_actions = dc_comment.find("div", attrs={"class":"actions"})
                        comment_like_list = re.findall(r"\d+", div_class_actions.text.strip())
                        
                        if comment_like_list:
                            comment_likes = int(comment_like_list[0])
                        else:
                            comment_likes = 0
                        comments[dict_primary_key]['likes'] = comment_likes  
                        
                        comm_no += 1
                        
        browser.execute_script("window.scrollTo({}, {});".format(i*SCREEN_HEIGHT_IN_PIXELS, \
                                                                 (i+1)*SCREEN_HEIGHT_IN_PIXELS))
        time.sleep(SCROLL_WAIT_TIME)
        
    return comments

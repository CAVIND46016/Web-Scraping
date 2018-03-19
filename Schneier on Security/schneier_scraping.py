"""
Contains the logic for scraping Schneier on Security
"""
import sys
import time
import urllib.request as urllib2
from datetime import datetime

from bs4 import BeautifulSoup

from util import connect_to_database_server

# Bruce Schneier's blog - Schneier on Security
BS_BLOG_PAGE = "https://www.schneier.com"

# PostgreSQL Database name
DATABASE = "Schneier"

# Recursion breakpoint definition
START_CUTOFF_DATE = datetime.strptime("1/1/2004", "%m/%d/%Y").date()
END_CUTOFF_DATE = datetime.now().date()

if START_CUTOFF_DATE > END_CUTOFF_DATE:
    raise ValueError('Cutoff start date is greater than end date.')

if END_CUTOFF_DATE > datetime.now().date():
    raise ValueError('Cutoff end date is greater than current date.')

# Tag filter
REQUIRED_TAGS = ['facebook', 'social media']

def get_date_time(datetimestr, _type):
    """
    converts text of the form '%B %d, %Y at %I:%M %p'
    into a python datetime object and returns date depending on '_type'
    type = 'article' or 'comment' ==> format string differs and so does the return value.
    """
    
    if _type == 'article':
        format_str = "Posted on %B %d, %Y at %I:%M %p"
        datetime_object = datetime.strptime(datetimestr, format_str)
        return datetime_object.date()
    else:
        format_str = "%B %d, %Y %I:%M %p"
        datetime_object = datetime.strptime(datetimestr, format_str)
        return datetime_object.strftime('%m/%d/%Y')

def extract_text(article_tag, _typ, _type='content'):
    """
    Extracts the article text contents
    """
    tmpstr = ""
    if _type == 'title':
        tag_list = ['p', 'blockquote', 'i', 'a']
    else:
        tag_list = ['p', 'blockquote', 'i', 'ul']
    
    for tag in tag_list:
        if _typ == 'A':
            _typ = article_tag.find_all(tag, class_=False, id=False, recursive=False)
        else:
            _typ = article_tag.find_all(tag, class_=False, id=False)
    
        for txt in _typ:
            if txt:
                tmpstr += txt.get_text() + " "
                
    return tmpstr


def scrape(bs_blog, conn, cur, i):  
    """
    Scrapes the blog page-by-page and inserts records to
    PostgreSQL page.
    """
    #Query the website and return the html to the variable 'page'
    page = urllib2.urlopen(bs_blog)
    #Parse the html in the 'page' variable, and store it in Beautiful Soup format
    soup = BeautifulSoup(page, "html.parser")

    article_tags = soup.find_all("div", attrs={"class":"article"})
    for article in article_tags:
        #If no comments, skip article.
        posted = article.find("p", attrs={"class": "posted"})
        if not posted:
            continue
        
        article_date = get_date_time([x.string for x in posted.find_all("a")][0], 'article')
        # apply the date filter
        if article_date < START_CUTOFF_DATE or article_date > END_CUTOFF_DATE:
            return 0

        # article title
        title_tag = article.find("h2", attrs={"class": "entry"})
        article_title = [x.string for x in title_tag][0]
        
        if not article_title:
            article_title = extract_text(title_tag, 'A', 'title')
        
        #tags
        entry_tag = article.find("p", attrs={"class": "entry-tags"})
        
        #article content
        article_string = extract_text(article, 'A')
        
        if entry_tag:
            tags = [x.string for x in entry_tag.find_all("a")]
        else:
            tags = ['']
        
        proceed_with_article = False
        if REQUIRED_TAGS:
            for elem in REQUIRED_TAGS:
                if article_title and elem in article_title:
                    proceed_with_article = True
                    continue
                
                if entry_tag: 
                    if len(list(set(REQUIRED_TAGS).intersection(tags))) != 0:
                        proceed_with_article = True
                        continue
                    
                if article_string and elem in article_string:
                    proceed_with_article = True
                    continue
        else:
            proceed_with_article = True
                
        if not proceed_with_article:
            continue
        
        href_comm = [x['href'] for x in posted.find_all("a")]
        if len(href_comm) <= 1:
            print("no comments: {}".format(bs_blog))
            continue
        
        aquery = "INSERT INTO a2017(articleno, link, title, text, tags, posteddate) \
                    VALUES (%s, %s, %s, %s, %s, %s);"
        adata = (i, bs_blog, article_title, article_string, ', '.join(tags), article_date)
        cur.execute(aquery, adata)
        
        href_comment_tag = href_comm[1]
        #comments
        cpage = urllib2.urlopen(href_comment_tag)
        csoup = BeautifulSoup(cpage, "html.parser")
        c_article_tags = csoup.find_all("article")
        # Since first article is not a comment.
        del c_article_tags[0]
         
        #loop through article comments
        for carticle in c_article_tags:
            commentcredit = carticle.find("p", attrs={"class": "commentcredit"})
            commenter = [x.text for x in commentcredit if x.name == "span"]
            posted_tags = [x.string for x in commentcredit.find_all("a")]
            comment_string = extract_text(carticle, 'C')
            cquery = "INSERT INTO c2017 (comments, articleno, commentedby, posteddate) \
                        VALUES (%s, %s, %s, %s);"
            cdata = (comment_string, i, commenter[0], \
                     get_date_time(posted_tags[len(posted_tags) - 1], 'comment'))
            cur.execute(cquery, cdata)

        i += 1
        earlier_entry = soup.find("a", attrs={"class": "earlier"})
        
        if not earlier_entry:
            print("no earlier entry: {}".format(bs_blog))
            return 0
        
        earlier_entry_href = earlier_entry['href']
        
    scrape(earlier_entry_href, conn, cur, i)

def main():
    """
    Entry-point for the function.
    """
    start_time = time.time()
    conn_obj = connect_to_database_server(DATABASE)
    
    if conn_obj == -1:
        print("Connection to PostgreSQL Database: {} failed.".format(DATABASE))
        sys.exit(0)
    else:
        conn = conn_obj[0]
        cur = conn_obj[1]
  
    scrape(BS_BLOG_PAGE, conn, cur, i=1)  
    
    conn.commit()
    cur.close()
    conn.close()
    print("Webdata scraped successfully in {} seconds.".format(time.time()-start_time))
    
if __name__ == "__main__":
    main()
    

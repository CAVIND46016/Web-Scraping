import urllib.request as urllib2
from bs4 import BeautifulSoup
from datetime import datetime
import sys
import time
from util import sendSMS, connectToDatabaseServer
import util

# Bruce Schneier's blog - Schneier on Security
bsblogpage = "https://www.schneier.com";

# PostGreSQL Database name
DATABASE = "full";

# Recursion breakpoint definition
cutoffdate = datetime.strptime("1/1/2017", "%m/%d/%Y").date()

# Tag filter
required_tags = ['facebook', 'social media']

def getDateTime(datetimestr, type):
    """
    converts text of the form '%B %d, %Y at %I:%M %p'
    into a python datetime object and returns date depending on 'type'
    type = 'article' or 'comment' ==> format string differs and so does the return value.
    """
    
    if(type == 'article'):
        format_str = "Posted on %B %d, %Y at %I:%M %p";
        datetime_object = datetime.strptime(datetimestr, format_str)
        return datetime_object.date();
    else:
        format_str = "%B %d, %Y %I:%M %p";
        datetime_object = datetime.strptime(datetimestr, format_str)
        return datetime_object.strftime('%m/%d/%Y');

def extractText(article_tag, t, type = 'content'):
    tmpstr = "";
    if type == 'title':
        tagList = ['p', 'blockquote', 'i', 'a'];
    else:
        tagList = ['p', 'blockquote', 'i', 'ul'];
    
    for tag in tagList:
        if(t == 'A'):
            t = article_tag.find_all(tag, class_=False, id=False, recursive = False);
        else:
            t = article_tag.find_all(tag, class_=False, id=False);
    
        for txt in t:
            if(txt):
                tmpstr += txt.get_text() + " ";
                
    return tmpstr;


def scrape(bs_blog, conn, cur, i):  
    #Query the website and return the html to the variable 'page'
    page = urllib2.urlopen(bs_blog)
    
    #Parse the html in the 'page' variable, and store it in Beautiful Soup format
    soup = BeautifulSoup(page, "html.parser")

    article_tags = soup.find_all("div", attrs={"class":"article"})
    for article in article_tags:
        proceedWithArticle = False;
        # article title
        title_tag = article.find("h2", attrs={"class": "entry"});
        article_title = [x.string for x in title_tag][0];
        
        if(article_title == None):
            article_title = extractText(title_tag, 'A', 'title');
        
        #tags
        entry_tag = article.find("p", attrs={"class": "entry-tags"})
        
        #article content
        article_string =  extractText(article, 'A');
        
        if(entry_tag):
            tags = [x.string for x in entry_tag.find_all("a")]; 
        else:
            tags = [''];
        
        if(required_tags != []):
            for elem in required_tags:
                if(article_title and elem in article_title):
                    proceedWithArticle = True;
                    continue;
                
                if(entry_tag): 
                    if(len(list(set(required_tags).intersection(tags))) != 0):
                        proceedWithArticle = True;
                        continue;
                    
                if(article_string and elem in article_string):
                    proceedWithArticle = True;
                    continue;
        else:
            proceedWithArticle = True;
                
        if(proceedWithArticle == False):
            continue;
                
        #datetime info and comments link
        posted = article.find("p", attrs={"class": "posted"})
        if(posted == None):
            continue;
        
        article_date = getDateTime([x.string for x in posted.find_all("a")][0], 'article');

        # Break recursion
        if(article_date < cutoffdate):
            return 0;
        
        h = [x['href'] for x in posted.find_all("a")];
        if(len(h) <= 1):
            print("no comments: {}".format(bs_blog))
            continue;
        
        aquery =  "INSERT INTO a2017(articleno, link, title, text, tags, posteddate) VALUES (%s, %s, %s, %s, %s, %s);"
        adata = (i, bs_blog, article_title, article_string, ', '.join(tags), article_date);
        cur.execute(aquery, adata);
        
        href_comment_tag = h[1];
        #comments
        cpage = urllib2.urlopen(href_comment_tag)
        csoup = BeautifulSoup(cpage, "html.parser")
        c_article_tags = csoup.find_all("article");
        # Since first article not a comment-article.
        del c_article_tags[0];
         
        #loop through article comments
        for carticle in c_article_tags:
            commentcredit = carticle.find("p", attrs={"class": "commentcredit"})
            commenter = [x.text for x in commentcredit if x.name == "span"];
            posted_tags = [x.string for x in commentcredit.find_all("a")];
            comment_string = extractText(carticle, 'C');
            cquery =  "INSERT INTO c2017 (comments, articleno, commentedby, posteddate) VALUES (%s, %s, %s, %s);"
            cdata = (comment_string, i, commenter[0], getDateTime(posted_tags[len(posted_tags) - 1], 'comment'));
            cur.execute(cquery, cdata);

        i += 1
       
        earlier_entry = soup.find("a", attrs={"class": "earlier"});
        
        if(not earlier_entry):
            print("no earlier entry: {}".format(bs_blog))
            return 0;
        
        earlier_entry_href = earlier_entry['href'];
        
    scrape(earlier_entry_href, conn, cur, i);

def main():
    s = time.time()
    
    conn_obj = connectToDatabaseServer(DATABASE);
    
    if(conn_obj == -1):
        print_text = "Connection to PostgreSQL Database: {} failed.".format(DATABASE);
        print(print_text);
        sendSMS(print_text + " at {}".format(datetime.now()));
        sys.exit(0);
    else:
        conn = conn_obj[0];
        cur = conn_obj[1];
  
    scrape(bsblogpage, conn, cur, i = 1);  
    
    conn.commit()
    cur.close()
    conn.close()
    
    print_text = "Webdata scraped successfully in {} seconds.".format(time.time()-s)
    print(print_text);
    
    sendSMS(print_text + " at {}".format(datetime.now())) 
    
if(__name__ == "__main__"):
    main();

from http.client import RemoteDisconnected

import requests
import random
import sqlite3
import time
from tqdm import tqdm

from fake_useragent import UserAgent
from bs4 import BeautifulSoup

from database import insert_tracker, last_record

page_link = "https://rutracker.org/forum/viewtopic.php?t={}"
# fist magnet at topic = 2142
topic_limit = 3_900_000

class Page:
    def __init__(self, id, link, title, size, body):
        self.id = id
        self.link = link # Magnet link
        self.title = title
        self.size = size
        self.body = body

    def hash(self):
        magnet = self.link.split(":")
        if len(magnet) == 4:
            return magnet[3].split("&")[0]
        else:
            return magnet[0]



def page(session, topic):
    response = session.get(url=page_link.format(topic),headers={'User-Agent': UserAgent().random, 'Content-Type': 'text/html; charset=utf-8'})
    if not response.ok:
        return "ERROR"

    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find(lambda tag: tag.get("class") == ["magnet-link"])
    title = soup.find(id="topic-title")

    if link is not None:
        download = soup.find(lambda tag: tag.get("class") == ["attach_link", "guest"]) # get Download block with 2 <li> elements
        size = download.find_all("li")[1].text.replace(" ", " ") # 2nd element is size
        post = soup.find(lambda tag: tag.get("class") == ["row1"])
        post_id = post.get("id").replace("post_", "p-")
        post_body = soup.find(id=post_id)
        return Page(topic, link.get("href"), title.text, size, post_body.text)
    elif title is not None:
        return Page(topic, "N/A", title.text, "N/A", "N/A")
    else:
        return "EMPTY"


def scraper(db):
    print("Let's run")
    max_errors = 20

    for run in range(max_errors):
        try:
            start = last_record(db)
            session = requests.Session()

            for topic_number in tqdm(range(start + 1, topic_limit), desc="Run " + str(run + 1)):
                result = page(session, topic_number)
                if result != "EMPTY":
                    print("id:{0} {1} title:{2}".format(result.id, result.link, result.title))
                    insert_tracker(db, result)

                time.sleep(random.randrange(1, 3) / 7)

            break # quit if topic_limit reached
        except Exception as ex:
            print("Connection terminated. Retry: {}".format(ex))
            time.sleep(5)
            pass # retry session and connection to site unless max_errors reached
    else:
        print("Unknown error")

    print("Finished")

if __name__ == "__main__":
    conn = None
    with open('sql/tables.sql', 'r') as sql_file:
        try:
            conn = sqlite3.connect("rutracker.sqlite")
            cur = conn.cursor()
            cur.execute(sql_file.read())
            conn.commit()
            scraper(conn)
        except sqlite3.Error as e:
            print(e)
        finally:
            if conn:
                conn.close()
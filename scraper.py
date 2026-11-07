from http.client import RemoteDisconnected

import random
import sqlite3
import time

from tqdm import tqdm

from bs4 import BeautifulSoup
from curl_cffi import requests
from patchright.sync_api import sync_playwright

from database import *

page_link = "https://rutracker.org/forum/viewtopic.php?t={}"
# fist magnet at topic = 2142
# from 3_800_000 and up to 100_000 is full, including N/A
topic_limit = 4_100_000

# Real Chrome profile used to pass the Cloudflare challenge. It is kept between runs,
# so the challenge usually needs to be solved only once in a while.
browser_profile = "browser_profile"
challenge_timeout = 60 # seconds to wait for the browser to pass the challenge
# Checks DOM only: patchright evaluates JS in an isolated world, so page globals are not visible
challenge_passed_js = """document.readyState === 'complete'
    && !document.getElementById('challenge-error-text')
    && !document.querySelector('script[src*="/cdn-cgi/challenge-platform/"]')"""

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



class CloudflareSession:
    """
    Rutracker is behind a Cloudflare managed challenge ("Just a moment..." page, HTTP 403),
    which needs JavaScript to pass, so a plain HTTP client can't get through on its own.
    When the challenge appears, a real Chrome window (driven by patchright, a Playwright fork
    patched against automation detection) solves it and gets the cf_clearance cookie.
    Pages are then fetched with curl_cffi, which sends Chrome's TLS/HTTP2 fingerprint and
    the same User-Agent as the browser, because Cloudflare ties cf_clearance to the User-Agent.
    """

    def __init__(self):
        self.session = requests.Session(impersonate="chrome")

    def get(self, url, timeout=10):
        response = self.session.get(url, timeout=timeout)
        if self.is_challenge(response):
            self.solve_challenge(url)
            response = self.session.get(url, timeout=timeout)
            if self.is_challenge(response):
                raise Exception("Cloudflare challenge is still shown after solving it in browser")
        return response

    @staticmethod
    def is_challenge(response):
        return response.headers.get("cf-mitigated") == "challenge"

    def solve_challenge(self, url):
        print("Cloudflare challenge detected, solving it in Chrome (if a checkbox appears in the window, click it)...")
        with sync_playwright() as p:
            # Headless Chrome is detected by Cloudflare, so a real window is opened
            context = p.chromium.launch_persistent_context(browser_profile, channel="chrome", headless=False, no_viewport=True)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(url, timeout=challenge_timeout * 1000)
                for _ in range(challenge_timeout):
                    try:
                        if page.evaluate(challenge_passed_js):
                            break
                    except Exception:
                        pass # page is reloading after the challenge is passed
                    time.sleep(1)
                else:
                    raise Exception("Cloudflare challenge was not solved in {} seconds".format(challenge_timeout))

                user_agent = page.evaluate("navigator.userAgent")
                cookies = context.cookies()
            finally:
                context.close()

        self.session.headers.update({"User-Agent": user_agent})
        for cookie in cookies:
            self.session.cookies.set(cookie["name"], cookie["value"], domain=cookie["domain"], path=cookie["path"])
        print("Cloudflare challenge solved")


def page(session, topic):
    response = session.get(page_link.format(topic), timeout=10)
    if not response.ok:
        return "ERROR"

    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find(lambda tag: tag.get("class") == ["magnet-link"])
    title = soup.find(id="topic-title")

    if link is not None:
        download = soup.find(lambda tag: tag.get("class") == ["attach_link", "guest"]) # get Download block, size is in the last <li> element
        size = download.find_all("li")[-1].text.strip().replace(" ", " ") # last element is size
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
            session = CloudflareSession()
            empties = check_empties(conn, start, topic_limit) # modify range here if you wish to re-check some interval

            for topic_number in tqdm(empties, desc="Run " + str(run + 1)):
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
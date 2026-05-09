from flask import Flask, jsonify, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import time
import re

app = Flask(__name__)

REGISTRATION = "FA23-BAI-001"
NEWS_SOURCE = "DAWN News Pakistan"

# DAWN RSS feeds to search across
RSS_FEEDS = [
    "https://www.dawn.com/feeds/latest-news",
    "https://www.dawn.com/feeds/home",
    "https://www.dawn.com/feeds/pakistan-news",
    "https://www.dawn.com/feeds/world-news",
    "https://www.dawn.com/feeds/business-news",
    "https://www.dawn.com/feeds/sport-news",
    "https://www.dawn.com/feeds/technology-news",
]

def get_chrome_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--window-size=1280,720")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(20)
    return driver

def summarize(text, num_sentences=4):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 40]
    return " ".join(sentences[:num_sentences]) if sentences else text[:600]

def fetch_rss(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        xml_data = resp.read()
        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        results = []
        for item in items:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            title = title_el.text if title_el is not None else ""
            link = link_el.text if link_el is not None else ""
            desc = desc_el.text if desc_el is not None else ""
            if title and link:
                results.append({"title": title, "link": link, "desc": desc})
        return results
    except Exception as e:
        print(f"[RSS ERROR] {url}: {e}")
        return []

def find_article_by_keyword(keyword):
    """Search all DAWN RSS feeds for keyword in title or description."""
    keyword_lower = keyword.lower()

    for feed_url in RSS_FEEDS:
        print(f"[RSS] Checking: {feed_url}")
        items = fetch_rss(feed_url)
        for item in items:
            if (keyword_lower in item["title"].lower() or
                keyword_lower in item["desc"].lower()):
                print(f"[RSS] MATCH: {item['title']} => {item['link']}")
                return item["link"]

    # If no keyword match, return first article from latest-news as fallback
    print(f"[RSS] No keyword match, using latest article")
    items = fetch_rss(RSS_FEEDS[0])
    if items:
        print(f"[RSS] Fallback: {items[0]['title']} => {items[0]['link']}")
        return items[0]["link"]

    return None

def scrape_article(article_url):
    """Scrape article content using one Chrome instance."""
    driver = get_chrome_driver()
    full_text = ""
    try:
        print(f"[ARTICLE] Loading: {article_url}")
        driver.get(article_url)
        time.sleep(4)
        print(f"[ARTICLE] Title: {driver.title}")

        if "just a moment" in driver.title.lower():
            try:
                meta = driver.find_element(By.CSS_SELECTOR, "meta[name='description']")
                full_text = meta.get_attribute("content") or ""
                print(f"[ARTICLE] Cloudflare block, meta: {full_text[:80]}")
            except:
                full_text = ""
        else:
            selectors = [
                "div.prism p",
                "div.template-story__body p",
                "div.story__content p",
                "article p",
            ]
            for sel in selectors:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                text = " ".join([e.text.strip() for e in els if len(e.text.strip()) > 40])
                if len(text) > 200:
                    full_text = text
                    print(f"[ARTICLE] {len(text)} chars via '{sel}'")
                    break

            if not full_text:
                all_p = driver.find_elements(By.TAG_NAME, "p")
                full_text = " ".join([p.text.strip() for p in all_p if len(p.text.strip()) > 40])
                print(f"[ARTICLE] Fallback p: {len(full_text)} chars")

    except Exception as e:
        print(f"[ARTICLE ERROR] {e}")
    finally:
        driver.quit()

    return full_text

def scrape_dawn(keyword):
    # Step 1: Find article URL from RSS (no browser, fast)
    article_url = find_article_by_keyword(keyword)
    if not article_url:
        return f"https://www.dawn.com/search?q={keyword}", "No article found."

    # Step 2: Scrape article with one Chrome instance
    content = scrape_article(article_url)
    summary = summarize(content) if content else "Content could not be extracted."
    return article_url, summary


@app.route("/get", methods=["GET"])
def get_news():
    keyword = request.args.get("keyword", "")
    if not keyword:
        return jsonify({"error": "keyword parameter is required"}), 400

    print(f"\n[REQUEST] keyword={keyword}")
    url, summary = scrape_dawn(keyword)

    return jsonify({
        "registration": REGISTRATION,
        "newssource": NEWS_SOURCE,
        "keyword": keyword,
        "url": url,
        "summary": summary
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000)

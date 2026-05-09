from flask import Flask, jsonify, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re

app = Flask(__name__)

REGISTRATION = "FA23-BAI-001"
NEWS_SOURCE = "DAWN News Pakistan"

def get_chrome_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    return driver

def summarize(text, num_sentences=4):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 40]
    return " ".join(sentences[:num_sentences]) if sentences else text[:600]

def scrape_dawn(keyword):
    driver = get_chrome_driver()
    result_url = ""
    summary = "Could not extract summary."

    try:
        # Use DAWN search
        search_url = f"https://www.dawn.com/search?q={keyword}&sort=date"
        print(f"[INFO] Searching: {search_url}")
        driver.get(search_url)
        time.sleep(4)

        # Find all links on the search results page
        links = driver.find_elements(By.TAG_NAME, "a")
        article_url = None

        for link in links:
            href = link.get_attribute("href") or ""
            # DAWN article URLs follow pattern: dawn.com/news/XXXXXXX
            if re.match(r'https://www\.dawn\.com/news/\d+', href):
                article_url = href
                print(f"[INFO] Found article: {article_url}")
                break

        if not article_url:
            # Fallback: try google search for dawn.com
            driver.get(f"https://www.google.com/search?q=site:dawn.com+{keyword}")
            time.sleep(3)
            links = driver.find_elements(By.CSS_SELECTOR, "a")
            for link in links:
                href = link.get_attribute("href") or ""
                if "dawn.com/news/" in href and "google" not in href:
                    article_url = href
                    break

        if not article_url:
            return search_url, "No article found for this keyword."

        result_url = article_url

        # Visit the article page
        print(f"[INFO] Visiting article: {result_url}")
        driver.get(result_url)
        time.sleep(4)

        # Try multiple selectors for DAWN article body
        content_selectors = [
            "div.template-story__body p",
            "div.story__content p",
            "article p",
            "div.content-area p",
            "section.story p",
            "div#article-content p",
        ]

        full_text = ""
        for selector in content_selectors:
            paragraphs = driver.find_elements(By.CSS_SELECTOR, selector)
            text = " ".join([
                p.text.strip() for p in paragraphs
                if len(p.text.strip()) > 40
            ])
            if len(text) > 200:
                full_text = text
                print(f"[INFO] Got text using selector: {selector} ({len(text)} chars)")
                break

        # Last resort fallback
        if not full_text:
            all_p = driver.find_elements(By.TAG_NAME, "p")
            full_text = " ".join([
                p.text.strip() for p in all_p
                if len(p.text.strip()) > 40
            ])
            print(f"[INFO] Fallback p tag text: {len(full_text)} chars")

        if full_text:
            summary = summarize(full_text)
        else:
            summary = "Article found but content could not be extracted."

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        summary = f"Scraping error: {str(e)}"
        result_url = result_url or f"https://www.dawn.com/search?q={keyword}"
    finally:
        driver.quit()

    return result_url, summary


@app.route("/get", methods=["GET"])
def get_news():
    keyword = request.args.get("keyword", "")
    if not keyword:
        return jsonify({"error": "keyword parameter is required"}), 400

    print(f"[REQUEST] keyword={keyword}")
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

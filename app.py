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
DAWN_SEARCH_URL = "https://www.dawn.com/search?q={keyword}"

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

def summarize(text, num_sentences=3):
    """Simple extractive summarizer — no external API needed."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
    return " ".join(sentences[:num_sentences]) if sentences else text[:500]

def scrape_dawn(keyword):
    driver = get_chrome_driver()
    result_url = ""
    summary = ""

    try:
        search_url = DAWN_SEARCH_URL.format(keyword=keyword)
        driver.get(search_url)
        wait = WebDriverWait(driver, 15)

        # Wait for search results and grab first article link
        first_link = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "article a, .story__link, h2 a, .search-result a")
            )
        )
        result_url = first_link.get_attribute("href")
        if result_url and not result_url.startswith("http"):
            result_url = "https://www.dawn.com" + result_url

        # Now visit the article
        driver.get(result_url)
        time.sleep(3)

        # Extract article body text
        paragraphs = driver.find_elements(By.CSS_SELECTOR, "article p, .story__content p, .template-story p")
        full_text = " ".join([p.text for p in paragraphs if p.text.strip()])

        if not full_text:
            # Fallback: grab all p tags
            paragraphs = driver.find_elements(By.TAG_NAME, "p")
            full_text = " ".join([p.text for p in paragraphs if len(p.text.strip()) > 40])

        summary = summarize(full_text)

    except Exception as e:
        summary = f"Error during scraping: {str(e)}"
        result_url = result_url or DAWN_SEARCH_URL.format(keyword=keyword)
    finally:
        driver.quit()

    return result_url, summary


@app.route("/get", methods=["GET"])
def get_news():
    keyword = request.args.get("keyword", "")
    if not keyword:
        return jsonify({"error": "keyword parameter is required"}), 400

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
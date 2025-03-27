import asyncio
import random
import requests
import feedparser
from playwright.async_api import async_playwright
from openai import OpenAI
from pymongo import MongoClient

# OpenAI API Client
openai_client = OpenAI(api_key="#enter your api key here")

# MongoDB connection
MONGO_URI = "mongodb://localhost:27017/"
client = MongoClient(MONGO_URI)
db = client["news_database"]  # Database name
summaries_collection = db["news_summaries"]  # Collection for storing summaries

# RSS Feeds
RSS_FEEDS = [
    "http://rss.cnn.com/rss/cnn_topstories.rss",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.theguardian.com/world/rss",
    "https://feeds.foxnews.com/foxnews/latest",
    "https://www.npr.org/rss/rss.php?id=1001",
]
MAX_URLS = 50
TIMEOUT = 5  # Timeout for RSS fetching

# Scrape text from a webpage
async def scrape_text(url):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await asyncio.wait_for(page.goto(url, wait_until="domcontentloaded"), timeout=30)
                text = await page.locator("body").inner_text()
                return {"url": url, "content": text}
            except asyncio.TimeoutError:
                return {"url": url, "error": "Timeout exceeded"}
            except Exception as e:
                return {"url": url, "error": str(e)}
            finally:
                await browser.close()
    except Exception as e:
        return {"url": url, "error": str(e)}

# Summarize and categorize
def summarize_and_categorize(content):
    prompt = f"""Summarize this news article in 100 words. 
    Provide a headline, classify it into one of the categories: 
    - Politics, Business, Technology, Science, Health, Sports, Entertainment, World News, Other.
    Also, extract the date and time mentioned in the article.

    Content: {content}"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    summary_text = response.choices[0].message.content
    lines = summary_text.split("\n")

    return {
        "headline": lines[0].strip() if lines else "No headline",
        "category": next((line.split(":")[-1].strip() for line in lines if "Category:" in line), "Other"),
        "date_time": next((line.split(":")[-1].strip() for line in lines if "Date:" in line), "Unknown"),
        "text": "\n".join(lines[1:]).strip() if len(lines) > 1 else "No summary"
    }

# Store result in MongoDB
def write_result(entry):
    if "summary" in entry:
        summaries_collection.insert_one({
            "url": entry["url"],
            "date_time": entry["summary"]["date_time"],
            "headline": entry["summary"]["headline"],
            "category": entry["summary"]["category"],
            "summary": entry["summary"]["text"]
        })
    else:
        summaries_collection.insert_one({
            "url": entry["url"],
            "error": entry.get("error", "No content found")
        })

# Fetch news URLs dynamically
def fetch_rss_urls():
    news_urls = set()
    for feed_url in RSS_FEEDS:
        if len(news_urls) >= MAX_URLS:
            break
        try:
            response = requests.get(feed_url, timeout=TIMEOUT)
            response.raise_for_status()
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                if len(news_urls) < MAX_URLS:
                    news_urls.add(entry.link)
                else:
                    break
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Skipping {feed_url} due to error: {e}")
    return list(news_urls)

# Main function
async def main():
    urls = fetch_rss_urls()
    random.shuffle(urls)

    for url in urls:
        print(f"🔄 Processing: {url}")
        data = await scrape_text(url)

        if "content" in data:
            print(f"✍️ Summarizing: {url}")
            data["summary"] = summarize_and_categorize(data["content"])

        write_result(data)
        print(f"✅ Done: {url}")

    print("📜 Scraping & summarization complete. Results saved in MongoDB.")

if __name__ == "__main__":
    asyncio.run(main())

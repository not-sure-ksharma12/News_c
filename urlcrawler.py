import feedparser
import requests
import random
from pymongo import MongoClient

# List of RSS feeds from various news sources
RSS_FEEDS = [
    "http://rss.cnn.com/rss/cnn_topstories.rss",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.theguardian.com/world/rss",
    "https://feeds.foxnews.com/foxnews/latest",
    "https://www.npr.org/rss/rss.php?id=1001",
]

MAX_URLS = 50  # Limit the number of URLs saved
TIMEOUT = 5  # Maximum time (in seconds) to wait for each RSS feed

# Connect to MongoDB
MONGO_URI = "mongodb://localhost:27017/"  # Change this if using MongoDB Atlas
client = MongoClient(MONGO_URI)
db = client["news_database"]  # Database name
collection = db["news_urls"]  # Collection name

# Clear existing URLs before inserting new ones
collection.delete_many({})

# Collect news URLs
news_urls = set()  # Use a set to avoid duplicates

for feed_url in RSS_FEEDS:
    if len(news_urls) >= MAX_URLS:
        break

    print(f"Fetching from: {feed_url}")

    try:
        response = requests.get(feed_url, timeout=TIMEOUT)
        response.raise_for_status()

        # Parse RSS feed
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            if len(news_urls) < MAX_URLS:
                news_urls.add(entry.link)
            else:
                break

    except (requests.exceptions.RequestException, Exception) as e:
        print(f"⚠️ Skipping {feed_url} due to error: {e}")

# Shuffle the URLs to mix sources
news_urls = list(news_urls)
random.shuffle(news_urls)

# Insert URLs into MongoDB
for url in news_urls:
    collection.insert_one({"url": url})

print(f"✅ Successfully stored {len(news_urls)} URLs in MongoDB!")
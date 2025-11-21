"""
Twitter Scraper Service - Refactored for DriverPool compatibility
Based on original twitter_web_app (5).py but optimized for concurrent use
"""
import sqlite3
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config.settings import DATABASE_PATH, MAX_TWEETS_PER_SCRAPE

logger = logging.getLogger(__name__)


class TwitterScraperService:
    """
    Twitter/X scraper that works with external WebDriver from pool.
    Thread-safe and designed for concurrent use.
    """

    def __init__(self, driver=None):
        """
        Initialize scraper.

        Args:
            driver: External WebDriver instance (from pool)
        """
        self.driver = driver
        self.init_database()

    def init_database(self):
        """Initialize database tables"""
        try:
            conn = sqlite3.connect(str(DATABASE_PATH))
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    profile_url TEXT,
                    scrape_interval_hours INTEGER DEFAULT 12,
                    last_scraped TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tweets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER,
                    tweet_id TEXT UNIQUE,
                    tweet_text TEXT,
                    tweet_url TEXT,
                    author TEXT,
                    timestamp TEXT,
                    language TEXT,
                    likes INTEGER DEFAULT 0,
                    retweets INTEGER DEFAULT 0,
                    replies INTEGER DEFAULT 0,
                    is_retweet BOOLEAN DEFAULT 0,
                    original_author TEXT,
                    scraped_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES profiles (id)
                )
            """)

            # Add columns if they don't exist
            try:
                cursor.execute("ALTER TABLE tweets ADD COLUMN is_retweet BOOLEAN DEFAULT 0")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE tweets ADD COLUMN original_author TEXT")
            except sqlite3.OperationalError:
                pass

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scrape_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER,
                    status TEXT,
                    tweets_found INTEGER,
                    tweets_new INTEGER,
                    error_message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES profiles (id)
                )
            """)

            conn.commit()
            conn.close()
            logger.info(f"Database initialized: {DATABASE_PATH}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def extract_tweet_data_from_dom_full(self, username):
        """
        Extract complete tweet data directly from DOM using JavaScript.
        """
        try:
            if not self.driver:
                return {}, []

            logger.debug("Extracting tweets from DOM using JavaScript...")

            extract_js = """
            (function() {
                const tweetData = {};
                const articles = document.querySelectorAll('article[data-testid="tweet"]');

                articles.forEach((article, index) => {
                    try {
                        const links = article.querySelectorAll('a[href*="/status/"]');
                        let tweetId = null;
                        let tweetUrl = null;
                        let foundUsername = null;

                        for (let link of links) {
                            const href = link.getAttribute('href');
                            if (href && href.includes('/status/')) {
                                const match = href.match(/\\/([^/]+)\\/status\\/(\\d+)/);
                                if (match) {
                                    foundUsername = match[1];
                                    tweetId = match[2];
                                    tweetUrl = href.startsWith('http') ? href : 'https://x.com' + href;
                                    break;
                                }
                            }
                        }

                        if (!tweetId) return;

                        let text = '';
                        let lang = '';
                        const textDiv = article.querySelector('div[data-testid="tweetText"]');
                        if (textDiv) {
                            const spans = textDiv.querySelectorAll('span[lang]');
                            if (spans.length > 0) {
                                text = Array.from(spans).map(s => s.textContent).join(' ').trim();
                                lang = spans[0].getAttribute('lang') || '';
                            } else {
                                text = textDiv.textContent.trim();
                            }
                        }

                        let likes = 0, retweets = 0, replies = 0;
                        const buttons = article.querySelectorAll('button');
                        buttons.forEach(button => {
                            const ariaLabel = button.getAttribute('aria-label') || '';
                            const digits = ariaLabel.match(/\\d+/);
                            if (digits) {
                                const num = parseInt(digits[0]);
                                if (ariaLabel.toLowerCase().includes('like') || ariaLabel.toLowerCase().includes('me gusta')) {
                                    likes = num;
                                } else if (ariaLabel.toLowerCase().includes('repost') || ariaLabel.toLowerCase().includes('retweet')) {
                                    retweets = num;
                                } else if (ariaLabel.toLowerCase().includes('repl') || ariaLabel.toLowerCase().includes('respuesta')) {
                                    replies = num;
                                }
                            }
                        });

                        let isRetweet = false;
                        let originalAuthor = null;
                        const articleText = article.textContent.toLowerCase();
                        if (articleText.includes('retweeted') || articleText.includes('retuiteado') || articleText.includes('retweet')) {
                            isRetweet = true;
                            const authorLinks = article.querySelectorAll('a[href^="/"]');
                            for (let link of authorLinks) {
                                const href = link.getAttribute('href');
                                if (href && !href.includes('/status/') && !href.includes('/i/')) {
                                    const match = href.match(/\\/([^/]+)/);
                                    if (match && match[1] !== foundUsername) {
                                        originalAuthor = match[1];
                                        break;
                                    }
                                }
                            }
                        }

                        if (text && text.length > 10) {
                            tweetData[tweetId] = {
                                username: foundUsername || '""" + username + """',
                                full_path: (foundUsername || '""" + username + """') + '/status/' + tweetId,
                                href: tweetUrl || 'https://x.com/' + (foundUsername || '""" + username + """') + '/status/' + tweetId,
                                text: text,
                                language: lang,
                                likes: likes,
                                retweets: retweets,
                                replies: replies,
                                is_retweet: isRetweet,
                                original_author: originalAuthor
                            };
                        }
                    } catch (e) {
                        console.error('Error processing article:', e);
                    }
                });

                return tweetData;
            })();
            """

            tweet_data_dict = self.driver.execute_script(extract_js)
            if not tweet_data_dict:
                return {}, []

            tweet_ids = list(tweet_data_dict.keys())
            logger.info(f"JavaScript extracted {len(tweet_ids)} tweets from DOM")

            return tweet_data_dict, tweet_ids

        except Exception as e:
            logger.error(f"Error extracting from DOM: {e}", exc_info=True)
            return {}, []

    def scrape_profile(self, username, max_tweets=None):
        """
        Scrape a Twitter/X profile.

        Args:
            username: Twitter username (without @)
            max_tweets: Maximum tweets to scrape (default from settings)

        Returns:
            dict: {'status': 'success'|'error', 'tweets_found': int, 'tweets_new': int}
        """
        if max_tweets is None:
            max_tweets = MAX_TWEETS_PER_SCRAPE

        url = f"https://x.com/{username}"

        logger.info(f"Starting scrape for @{username}")

        try:
            if not self.driver:
                return {"status": "error", "message": "No driver available"}

            # Navigate to profile
            self.driver.get(url)
            logger.info(f"Waiting for initial load of @{username}...")
            time.sleep(8)

            # Check if login required
            if "login" in self.driver.current_url or "i/flow/login" in self.driver.current_url:
                return {"status": "error", "message": "Authentication required"}

            # Wait for tweets to load
            wait = WebDriverWait(self.driver, 20)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']")))
                logger.info("Tweets detected on page")
            except:
                logger.warning("No tweets detected with data-testid='tweet'")

            time.sleep(12)

            # Do scrolling to load more tweets
            logger.info("Scrolling to load tweets...")
            for i in range(3):
                try:
                    self.driver.execute_script("window.scrollBy(0, 500);")
                    time.sleep(3)
                except Exception as e:
                    logger.warning(f"Error during scroll {i+1}: {e}")
                    break

            # Scroll back to top
            try:
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(8)
            except Exception as e:
                logger.warning(f"Error scrolling to top: {e}")

            # Progressive scrolling
            logger.info("Progressive scrolling to load more tweets...")
            last_height = 0
            scroll_attempts = 0
            max_scrolls = 15

            for i in range(max_scrolls):
                try:
                    self.driver.execute_script("window.scrollBy(0, 1000);")
                    time.sleep(6)

                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        scroll_attempts += 1
                        if scroll_attempts >= 3:
                            logger.info("No more content, stopping scrolls")
                            break
                    else:
                        scroll_attempts = 0
                        last_height = new_height

                    current_count = self.driver.execute_script(
                        'return document.querySelectorAll(\'article[data-testid="tweet"]\').length;'
                    )
                    logger.debug(f"Scroll {i+1}/{max_scrolls} - Height: {new_height} - Tweets: {current_count}")

                except Exception as e:
                    logger.warning(f"Error during scroll {i+1}: {e}")
                    break

            # Scroll back to top to process recent tweets
            logger.info("Scrolling back to top to process tweets...")
            try:
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(10)
            except Exception as e:
                logger.warning(f"Error scrolling to top: {e}")

            # Extract tweets from DOM
            logger.info("Extracting tweets from DOM...")
            tweet_data_dict_full, tweet_ids_full = self.extract_tweet_data_from_dom_full(username)

            if not tweet_ids_full:
                logger.warning("No tweets found")

                # Log error
                conn = sqlite3.connect(str(DATABASE_PATH))
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM profiles WHERE username = ?", (username,))
                result = cursor.fetchone()
                profile_id = result[0] if result else None
                conn.close()

                error_msg = "No tweets found in DOM"

                if profile_id:
                    conn = sqlite3.connect(str(DATABASE_PATH))
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO scrape_logs (profile_id, status, error_message)
                        VALUES (?, ?, ?)
                    """, (profile_id, 'error', error_msg))
                    conn.commit()
                    conn.close()

                return {"status": "error", "message": error_msg}

            logger.info(f"Found {len(tweet_ids_full)} tweets")

            # Limit to max_tweets
            tweet_ids = tweet_ids_full[:max_tweets]

            # Save to database
            conn = sqlite3.connect(str(DATABASE_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM profiles WHERE username = ?", (username,))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return {"status": "error", "message": "Profile not found in database"}
            profile_id = result[0]

            tweets_found = 0
            tweets_new = 0
            seen_ids = set()

            logger.info(f"Processing {len(tweet_ids)} tweets...")
            for idx, tweet_id in enumerate(tweet_ids):
                try:
                    if tweet_id in seen_ids:
                        continue
                    seen_ids.add(tweet_id)

                    # Check if exists
                    cursor.execute("SELECT id FROM tweets WHERE tweet_id = ?", (tweet_id,))
                    if cursor.fetchone():
                        if idx < 10:
                            logger.debug(f"Tweet {idx+1}: Already in DB (ID: {tweet_id})")
                        continue

                    # Get tweet data
                    if tweet_id not in tweet_data_dict_full:
                        continue

                    tweet_data = tweet_data_dict_full[tweet_id]
                    text = tweet_data.get('text', '').strip()
                    lang = tweet_data.get('language', '')
                    likes = tweet_data.get('likes', 0)
                    retweets = tweet_data.get('retweets', 0)
                    replies = tweet_data.get('replies', 0)
                    is_retweet = tweet_data.get('is_retweet', False)
                    original_author = tweet_data.get('original_author', None)
                    tweet_url = tweet_data.get('href', f"https://x.com/{username}/status/{tweet_id}")

                    # Validate
                    if not text or len(text) < 10:
                        continue

                    if "Traducido de" in text or "Translated from" in text:
                        continue

                    tweets_found += 1

                    # Insert
                    cursor.execute("""
                        INSERT INTO tweets (profile_id, tweet_id, tweet_text, tweet_url, author, timestamp, language, likes, retweets, replies, is_retweet, original_author)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        profile_id, tweet_id, text, tweet_url, username,
                        datetime.now().isoformat(), lang, likes, retweets, replies,
                        is_retweet, original_author
                    ))
                    tweets_new += 1

                    rt_indicator = " [RT]" if is_retweet else ""
                    if is_retweet and original_author:
                        rt_indicator = f" [RT de @{original_author}]"
                    logger.info(f"✓ Tweet {tweets_new} NEW{rt_indicator} (ID: {tweet_id}): {text[:60]}...")

                except Exception as e:
                    logger.error(f"Error processing tweet {idx+1} (ID: {tweet_id}): {e}")
                    continue

            cursor.execute(
                "UPDATE profiles SET last_scraped = ? WHERE id = ?",
                (datetime.now().isoformat(), profile_id)
            )
            cursor.execute("""
                INSERT INTO scrape_logs (profile_id, status, tweets_found, tweets_new)
                VALUES (?, ?, ?, ?)
            """, (profile_id, 'success', tweets_found, tweets_new))
            conn.commit()
            conn.close()

            logger.info(f"Scrape complete: {tweets_new} new tweets from {tweets_found} processed")

            return {
                "status": "success",
                "tweets_found": tweets_found,
                "tweets_new": tweets_new
            }

        except Exception as e:
            logger.error(f"Error scraping profile: {e}", exc_info=True)

            try:
                conn = sqlite3.connect(str(DATABASE_PATH))
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM profiles WHERE username = ?", (username,))
                result = cursor.fetchone()
                if result:
                    cursor.execute("""
                        INSERT INTO scrape_logs (profile_id, status, error_message)
                        VALUES (?, ?, ?)
                    """, (result[0], 'error', str(e)))
                    conn.commit()
                conn.close()
            except:
                pass

            return {"status": "error", "message": str(e)}

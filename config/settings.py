"""
Configuration settings for Twitter Scraper
"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Database
DATABASE_PATH = os.getenv('DATABASE_PATH', BASE_DIR / 'twitter_scraper.db')

# Chrome settings
CHROME_PROFILE_DIR = BASE_DIR / 'chrome_profiles'
HEADLESS = os.getenv('HEADLESS', 'True').lower() == 'true'

# Driver Pool settings
DRIVER_POOL_SIZE = int(os.getenv('DRIVER_POOL_SIZE', '3'))
DRIVER_TIMEOUT = int(os.getenv('DRIVER_TIMEOUT', '300'))  # 5 minutes

# Celery settings
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 600  # 10 minutes max per task
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # One task at a time per worker

# Flask settings
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

# Scraping settings
MAX_TWEETS_PER_SCRAPE = int(os.getenv('MAX_TWEETS_PER_SCRAPE', '100'))
SCRAPE_SCROLL_COUNT = int(os.getenv('SCRAPE_SCROLL_COUNT', '15'))
SCRAPE_SCROLL_DELAY = int(os.getenv('SCRAPE_SCROLL_DELAY', '6'))

# Monitoring settings
ENABLE_METRICS = os.getenv('ENABLE_METRICS', 'True').lower() == 'true'

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

# Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Rate limiting
RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'True').lower() == 'true'
RATE_LIMIT_PER_HOUR = int(os.getenv('RATE_LIMIT_PER_HOUR', '100'))

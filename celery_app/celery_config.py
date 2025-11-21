"""
Celery configuration for async task processing
"""
from celery import Celery
from kombu import Queue
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CELERY_TASK_TRACK_STARTED,
    CELERY_TASK_TIME_LIMIT,
    CELERY_WORKER_PREFETCH_MULTIPLIER
)

# Create Celery app
celery_app = Celery('twitter_scraper')

# Configure Celery
celery_app.conf.update(
    broker_url=CELERY_BROKER_URL,
    result_backend=CELERY_RESULT_BACKEND,
    task_track_started=CELERY_TASK_TRACK_STARTED,
    task_time_limit=CELERY_TASK_TIME_LIMIT,
    worker_prefetch_multiplier=CELERY_WORKER_PREFETCH_MULTIPLIER,

    # Task serialization
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,

    # Task routing
    task_routes={
        'celery_app.tasks.scrape_profile_task': {'queue': 'scraping'},
        'celery_app.tasks.scrape_multiple_profiles_task': {'queue': 'scraping'},
    },

    # Task queues
    task_queues=(
        Queue('scraping', routing_key='scraping'),
        Queue('default', routing_key='default'),
    ),

    # Result expiration
    result_expires=3600,  # 1 hour

    # Task acks late (for reliability)
    task_acks_late=True,

    # Worker settings
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
    worker_disable_rate_limits=False,

    # Task result settings
    result_extended=True,  # Store task args/kwargs
)

# Import tasks (must be after app configuration)
from celery_app import tasks

__all__ = ['celery_app']

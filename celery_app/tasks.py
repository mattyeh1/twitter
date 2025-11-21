"""
Celery tasks for async scraping operations
"""
import logging
import time
from datetime import datetime
from celery import Task
from celery_app.celery_config import celery_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScraperTask(Task):
    """Base task with error handling and driver management"""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"Task {task_id} failed: {exc}")
        logger.error(f"Exception info: {einfo}")

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(f"Task {task_id} completed successfully")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry"""
        logger.warning(f"Task {task_id} retrying due to: {exc}")


@celery_app.task(
    base=ScraperTask,
    bind=True,
    name='celery_app.tasks.scrape_profile_task',
    max_retries=3,
    default_retry_delay=60
)
def scrape_profile_task(self, username, max_tweets=100):
    """
    Scrape a single Twitter/X profile asynchronously.

    Args:
        username: Twitter username to scrape
        max_tweets: Maximum number of tweets to scrape

    Returns:
        dict: Scraping results with status, tweets_found, tweets_new
    """
    from app.services.scraper_service import TwitterScraperService
    from app.services.driver_pool import get_driver_pool
    from config.settings import DRIVER_POOL_SIZE, HEADLESS, CHROME_PROFILE_DIR

    logger.info(f"Starting scrape task for @{username}")

    # Update task state to show progress
    self.update_state(
        state='PROGRESS',
        meta={
            'current': 0,
            'total': 100,
            'status': f'Initializing scraper for @{username}...'
        }
    )

    try:
        # Get driver pool
        driver_pool = get_driver_pool(
            pool_size=DRIVER_POOL_SIZE,
            headless=HEADLESS,
            profile_dir=str(CHROME_PROFILE_DIR)
        )

        # Update state
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 10,
                'total': 100,
                'status': f'Acquiring driver from pool...'
            }
        )

        # Acquire driver from pool
        with driver_pool.acquire(timeout=60) as driver:
            logger.info(f"Acquired driver for @{username}")

            # Update state
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': 20,
                    'total': 100,
                    'status': f'Scraping @{username}...'
                }
            )

            # Create scraper instance with this driver
            scraper = TwitterScraperService(driver=driver)

            # Scrape profile
            result = scraper.scrape_profile(username, max_tweets=max_tweets)

            # Update state
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': 90,
                    'total': 100,
                    'status': f'Finalizing scrape for @{username}...'
                }
            )

            logger.info(f"Scrape completed for @{username}: {result}")

            # Return result
            return {
                'status': result.get('status', 'unknown'),
                'username': username,
                'tweets_found': result.get('tweets_found', 0),
                'tweets_new': result.get('tweets_new', 0),
                'message': result.get('message', ''),
                'completed_at': datetime.now().isoformat()
            }

    except Exception as exc:
        logger.error(f"Error scraping @{username}: {exc}", exc_info=True)

        # Retry on certain errors
        if 'timeout' in str(exc).lower() or 'connection' in str(exc).lower():
            raise self.retry(exc=exc)

        # Return error result
        return {
            'status': 'error',
            'username': username,
            'tweets_found': 0,
            'tweets_new': 0,
            'message': str(exc),
            'completed_at': datetime.now().isoformat()
        }


@celery_app.task(
    base=ScraperTask,
    bind=True,
    name='celery_app.tasks.scrape_multiple_profiles_task'
)
def scrape_multiple_profiles_task(self, usernames, max_tweets=100):
    """
    Scrape multiple profiles sequentially.

    Args:
        usernames: List of Twitter usernames
        max_tweets: Max tweets per profile

    Returns:
        dict: Results for all profiles
    """
    logger.info(f"Starting batch scrape for {len(usernames)} profiles")

    results = []
    total = len(usernames)

    for idx, username in enumerate(usernames):
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': idx,
                'total': total,
                'status': f'Scraping @{username} ({idx+1}/{total})...'
            }
        )

        # Scrape this profile
        result = scrape_profile_task.apply(args=[username, max_tweets])
        results.append(result.get())

        # Small delay between profiles
        if idx < total - 1:
            time.sleep(5)

    return {
        'status': 'completed',
        'total_profiles': total,
        'results': results,
        'completed_at': datetime.now().isoformat()
    }


@celery_app.task(name='celery_app.tasks.cleanup_old_tasks')
def cleanup_old_tasks():
    """
    Periodic task to clean up old task results from Redis.
    Run this daily via celery beat.
    """
    from celery.result import AsyncResult
    from celery_app.celery_config import celery_app

    logger.info("Running cleanup of old task results")

    # This would iterate through old task IDs and forget them
    # Implementation depends on your task tracking strategy

    return {'status': 'cleanup_completed', 'timestamp': datetime.now().isoformat()}


@celery_app.task(name='celery_app.tasks.health_check')
def health_check():
    """
    Simple health check task for monitoring.
    """
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'worker': 'celery'
    }

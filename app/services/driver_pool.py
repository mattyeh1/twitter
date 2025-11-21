"""
Selenium WebDriver Pool for concurrent scraping
Manages multiple Chrome instances safely
"""
import os
import logging
import time
from queue import Queue, Empty
from threading import Lock
from contextlib import contextmanager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

logger = logging.getLogger(__name__)


class DriverPool:
    """
    Thread-safe pool of Selenium WebDriver instances.
    Allows multiple concurrent scraping operations.
    """

    def __init__(self, pool_size=3, headless=True, profile_dir='chrome_profiles'):
        """
        Initialize driver pool.

        Args:
            pool_size: Number of Chrome instances to maintain
            headless: Run Chrome in headless mode
            profile_dir: Directory for Chrome user profiles
        """
        self.pool_size = pool_size
        self.headless = headless
        self.profile_dir = profile_dir
        self.drivers = Queue(maxsize=pool_size)
        self.lock = Lock()
        self.active_count = 0
        self.total_created = 0
        self.total_acquired = 0
        self.total_released = 0

        # Create profile directory if it doesn't exist
        os.makedirs(profile_dir, exist_ok=True)

        logger.info(f"Initializing DriverPool with {pool_size} drivers")

        # Pre-populate pool with drivers
        for i in range(pool_size):
            try:
                driver = self._create_driver(driver_id=i)
                self.drivers.put(driver)
                self.total_created += 1
                logger.info(f"Created driver {i+1}/{pool_size}")
            except Exception as e:
                logger.error(f"Failed to create driver {i}: {e}")

    def _create_driver(self, driver_id):
        """
        Create a new Chrome WebDriver instance.
        Each driver gets its own user profile to avoid conflicts.
        """
        chrome_options = Options()

        # Each driver gets its own profile directory
        profile_path = os.path.abspath(
            os.path.join(self.profile_dir, f'profile_{driver_id}')
        )
        chrome_options.add_argument(f'--user-data-dir={profile_path}')

        if self.headless:
            chrome_options.add_argument('--headless=new')

        # Standard Chrome options for stability
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument(f'--remote-debugging-port={9223 + driver_id}')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')

        # Create driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(60)

        # Store driver ID for tracking
        driver.driver_id = driver_id

        return driver

    @contextmanager
    def acquire(self, timeout=30):
        """
        Acquire a driver from the pool (context manager).

        Usage:
            with driver_pool.acquire() as driver:
                driver.get("https://example.com")

        Args:
            timeout: Max seconds to wait for available driver

        Yields:
            WebDriver instance
        """
        driver = None
        try:
            # Get driver from pool (blocks if all busy)
            driver = self.drivers.get(timeout=timeout)

            with self.lock:
                self.active_count += 1
                self.total_acquired += 1

            driver_id = getattr(driver, 'driver_id', 'unknown')
            logger.debug(f"Acquired driver {driver_id} (active: {self.active_count})")

            # Verify driver is still functional
            try:
                _ = driver.current_url
            except WebDriverException:
                logger.warning(f"Driver {driver_id} was dead, recreating...")
                try:
                    driver.quit()
                except:
                    pass
                driver = self._create_driver(driver_id)

            yield driver

        except Empty:
            logger.error(f"Timeout waiting for driver (timeout={timeout}s)")
            raise TimeoutError(f"No driver available within {timeout} seconds")

        finally:
            if driver:
                # Return driver to pool
                with self.lock:
                    self.active_count -= 1
                    self.total_released += 1

                # Clean up driver state before returning to pool
                try:
                    # Clear cookies and cache
                    driver.delete_all_cookies()
                    # Navigate to blank page to free resources
                    driver.get('about:blank')
                except Exception as e:
                    logger.warning(f"Error cleaning driver: {e}")

                self.drivers.put(driver)
                driver_id = getattr(driver, 'driver_id', 'unknown')
                logger.debug(f"Released driver {driver_id} (active: {self.active_count})")

    def get_driver(self, timeout=30):
        """
        Get a driver from pool (non-context manager version).
        Must call release_driver() when done!

        Returns:
            WebDriver instance
        """
        try:
            driver = self.drivers.get(timeout=timeout)

            with self.lock:
                self.active_count += 1
                self.total_acquired += 1

            # Verify driver is functional
            try:
                _ = driver.current_url
            except WebDriverException:
                driver_id = getattr(driver, 'driver_id', 0)
                logger.warning(f"Driver {driver_id} was dead, recreating...")
                try:
                    driver.quit()
                except:
                    pass
                driver = self._create_driver(driver_id)

            return driver

        except Empty:
            raise TimeoutError(f"No driver available within {timeout} seconds")

    def release_driver(self, driver):
        """
        Return a driver to the pool.
        """
        if driver:
            with self.lock:
                self.active_count -= 1
                self.total_released += 1

            # Clean driver state
            try:
                driver.delete_all_cookies()
                driver.get('about:blank')
            except:
                pass

            self.drivers.put(driver)

    def shutdown(self):
        """
        Shutdown all drivers in the pool.
        """
        logger.info("Shutting down DriverPool...")

        drivers_to_close = []

        # Drain the queue
        while not self.drivers.empty():
            try:
                driver = self.drivers.get_nowait()
                drivers_to_close.append(driver)
            except Empty:
                break

        # Close all drivers
        for driver in drivers_to_close:
            try:
                driver.quit()
                logger.info(f"Closed driver {getattr(driver, 'driver_id', 'unknown')}")
            except Exception as e:
                logger.error(f"Error closing driver: {e}")

        logger.info(f"DriverPool shutdown complete. Stats: "
                   f"created={self.total_created}, "
                   f"acquired={self.total_acquired}, "
                   f"released={self.total_released}")

    def get_stats(self):
        """
        Get pool statistics.

        Returns:
            dict with pool stats
        """
        return {
            'pool_size': self.pool_size,
            'available': self.drivers.qsize(),
            'active': self.active_count,
            'total_created': self.total_created,
            'total_acquired': self.total_acquired,
            'total_released': self.total_released
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


# Global driver pool instance (lazy initialization)
_driver_pool = None
_pool_lock = Lock()


def get_driver_pool(pool_size=3, headless=True, profile_dir='chrome_profiles'):
    """
    Get or create the global driver pool instance.
    Thread-safe singleton pattern.
    """
    global _driver_pool

    if _driver_pool is None:
        with _pool_lock:
            # Double-check locking
            if _driver_pool is None:
                _driver_pool = DriverPool(
                    pool_size=pool_size,
                    headless=headless,
                    profile_dir=profile_dir
                )

    return _driver_pool


def shutdown_driver_pool():
    """
    Shutdown the global driver pool.
    """
    global _driver_pool

    if _driver_pool:
        _driver_pool.shutdown()
        _driver_pool = None

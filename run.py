"""
Main entry point for Twitter Scraper application
"""
import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from config.settings import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, LOG_LEVEL

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Run the application"""
    logger.info("="*60)
    logger.info("Twitter Scraper - Advanced System")
    logger.info("="*60)
    logger.info(f"Starting Flask app on {FLASK_HOST}:{FLASK_PORT}")
    logger.info(f"Debug mode: {FLASK_DEBUG}")
    logger.info("="*60)

    # Create Flask app
    app = create_app()

    # Run app
    try:
        app.run(
            host=FLASK_HOST,
            port=FLASK_PORT,
            debug=FLASK_DEBUG,
            use_reloader=False  # Disable reloader to avoid issues with driver pool
        )
    except KeyboardInterrupt:
        logger.info("\nShutting down...")

        # Cleanup driver pool
        from app.services.driver_pool import shutdown_driver_pool
        shutdown_driver_pool()

        logger.info("Goodbye!")

if __name__ == '__main__':
    main()

"""
Flask application factory
"""
import logging
from flask import Flask
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)

    # Load configuration
    from config.settings import FLASK_SECRET_KEY
    app.config['SECRET_KEY'] = FLASK_SECRET_KEY

    # Enable CORS
    CORS(app)

    # Register blueprints
    from app.routes import dashboard, api
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(api.bp, url_prefix='/api')

    # Initialize database
    from app.services.scraper_service import TwitterScraperService
    scraper = TwitterScraperService()
    scraper.init_database()

    return app

#!/bin/bash
# Start Twitter Scraper locally (without Docker)

echo "========================================="
echo "Twitter Scraper - Local Startup"
echo "========================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your settings!"
fi

# Check if Redis is running
echo "Checking Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running!"
    echo "Please install and start Redis:"
    echo "  - Ubuntu/Debian: sudo apt-get install redis-server && sudo systemctl start redis"
    echo "  - macOS: brew install redis && brew services start redis"
    echo "  - Windows: Download from https://redis.io/download"
    exit 1
fi
echo "✓ Redis is running"

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p logs chrome_profiles

# Start services in separate terminals
echo ""
echo "========================================="
echo "Starting services..."
echo "========================================="

# Start Flask app
echo "Starting Flask web app..."
gnome-terminal -- bash -c "source venv/bin/activate 2>/dev/null; python run.py; exec bash" 2>/dev/null || \
    osascript -e 'tell app "Terminal" to do script "cd '$(pwd)' && python run.py"' 2>/dev/null || \
    start cmd /k "python run.py" 2>/dev/null || \
    echo "⚠️  Please start Flask manually: python run.py"

sleep 2

# Start Celery worker
echo "Starting Celery worker..."
gnome-terminal -- bash -c "source venv/bin/activate 2>/dev/null; celery -A celery_app.celery_config worker --loglevel=info --concurrency=3; exec bash" 2>/dev/null || \
    osascript -e 'tell app "Terminal" to do script "cd '$(pwd)' && celery -A celery_app.celery_config worker --loglevel=info --concurrency=3"' 2>/dev/null || \
    start cmd /k "celery -A celery_app.celery_config worker --loglevel=info --concurrency=3" 2>/dev/null || \
    echo "⚠️  Please start Celery manually: celery -A celery_app.celery_config worker --loglevel=info --concurrency=3"

sleep 2

# Start Flower (optional)
echo "Starting Flower monitoring dashboard..."
gnome-terminal -- bash -c "source venv/bin/activate 2>/dev/null; celery -A celery_app.celery_config flower --port=5555; exec bash" 2>/dev/null || \
    osascript -e 'tell app "Terminal" to do script "cd '$(pwd)' && celery -A celery_app.celery_config flower --port=5555"' 2>/dev/null || \
    start cmd /k "celery -A celery_app.celery_config flower --port=5555" 2>/dev/null || \
    echo "⚠️  Please start Flower manually: celery -A celery_app.celery_config flower --port=5555"

echo ""
echo "========================================="
echo "✓ All services started!"
echo "========================================="
echo ""
echo "Access the application:"
echo "  - Dashboard: http://localhost:5000"
echo "  - Flower (Celery monitoring): http://localhost:5555"
echo ""
echo "Press Ctrl+C to stop all services"
echo "========================================="

# Wait
read -p "Press Enter to stop all services..."

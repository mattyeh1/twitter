"""
API endpoints for async scraping operations
"""
import logging
from flask import Blueprint, jsonify, request
from celery.result import AsyncResult
from celery_app.celery_config import celery_app
from celery_app.tasks import scrape_profile_task, health_check
from app.services.driver_pool import get_driver_pool

logger = logging.getLogger(__name__)

bp = Blueprint('api', __name__)


@bp.route('/scrape', methods=['POST'])
def scrape_profile():
    """
    Trigger async scraping for a profile.

    POST /api/scrape
    Body: {"username": "elonmusk", "max_tweets": 100}

    Returns:
        {"task_id": "abc123", "status": "queued", "username": "elonmusk"}
    """
    data = request.get_json()

    if not data or 'username' not in data:
        return jsonify({'error': 'Missing username'}), 400

    username = data['username'].strip().replace('@', '')
    max_tweets = data.get('max_tweets', 100)

    # Validate username
    if not username or len(username) < 1:
        return jsonify({'error': 'Invalid username'}), 400

    # Trigger async task
    task = scrape_profile_task.delay(username, max_tweets)

    logger.info(f"Scraping task queued for @{username}, task_id={task.id}")

    return jsonify({
        'task_id': task.id,
        'status': 'queued',
        'username': username,
        'message': f'Scraping queued for @{username}'
    }), 202


@bp.route('/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """
    Get status of a scraping task.

    GET /api/task/<task_id>

    Returns:
        {"status": "PENDING|PROGRESS|SUCCESS|FAILURE", "result": {...}}
    """
    task = AsyncResult(task_id, app=celery_app)

    if task.state == 'PENDING':
        response = {
            'status': 'pending',
            'message': 'Task is waiting in queue...'
        }
    elif task.state == 'PROGRESS':
        response = {
            'status': 'progress',
            'current': task.info.get('current', 0),
            'total': task.info.get('total', 100),
            'message': task.info.get('status', 'Processing...')
        }
    elif task.state == 'SUCCESS':
        response = {
            'status': 'success',
            'result': task.result
        }
    elif task.state == 'FAILURE':
        response = {
            'status': 'failed',
            'error': str(task.info)
        }
    else:
        response = {
            'status': task.state.lower(),
            'message': 'Task in unknown state'
        }

    return jsonify(response)


@bp.route('/pool/stats', methods=['GET'])
def get_pool_stats():
    """
    Get driver pool statistics.

    GET /api/pool/stats

    Returns:
        {"pool_size": 3, "available": 2, "active": 1, ...}
    """
    try:
        pool = get_driver_pool()
        stats = pool.get_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting pool stats: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint.

    GET /api/health

    Returns:
        {"status": "healthy", ...}
    """
    try:
        # Check Celery
        result = health_check.delay()
        celery_health = result.get(timeout=5)

        # Check driver pool
        pool = get_driver_pool()
        pool_stats = pool.get_stats()

        return jsonify({
            'status': 'healthy',
            'celery': celery_health,
            'driver_pool': pool_stats
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

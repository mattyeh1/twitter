"""
Dashboard routes for web interface
"""
import sqlite3
import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from config.settings import DATABASE_PATH
from celery_app.tasks import scrape_profile_task

logger = logging.getLogger(__name__)

bp = Blueprint('dashboard', __name__)


@bp.route('/')
def home():
    """Dashboard home page"""
    try:
        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()

        # Get statistics
        cursor.execute("SELECT COUNT(*) FROM profiles")
        total_profiles = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM profiles WHERE is_active = 1")
        active_profiles = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tweets")
        total_tweets = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM tweets
            WHERE DATE(scraped_date) = DATE('now')
        """)
        today_tweets = cursor.fetchone()[0]

        # Get profiles
        cursor.execute("""
            SELECT p.id, p.username, p.scrape_interval_hours, p.last_scraped, p.is_active,
                   COUNT(t.id) as tweet_count
            FROM profiles p
            LEFT JOIN tweets t ON p.id = t.profile_id
            GROUP BY p.id
            ORDER BY p.added_date DESC
        """)

        profiles = []
        for row in cursor.fetchall():
            profiles.append({
                'id': row[0],
                'username': row[1],
                'scrape_interval_hours': row[2],
                'last_scraped': row[3][:16] if row[3] else None,
                'is_active': row[4],
                'tweet_count': row[5]
            })

        conn.close()

        stats = {
            'total_profiles': total_profiles,
            'active_profiles': active_profiles,
            'total_tweets': total_tweets,
            'today_tweets': today_tweets
        }

        return render_template('dashboard.html', stats=stats, profiles=profiles)

    except Exception as e:
        logger.error(f"Error loading dashboard: {e}", exc_info=True)
        return f"Error: {e}", 500


@bp.route('/add_profile', methods=['POST'])
def add_profile():
    """Add new profile to monitor"""
    username = request.form.get('username', '').strip().replace('@', '')
    interval = int(request.form.get('interval', 12))

    if not username:
        return jsonify({'error': 'Username required'}), 400

    try:
        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO profiles (username, profile_url, scrape_interval_hours)
            VALUES (?, ?, ?)
        """, (username, f"https://x.com/{username}", interval))

        conn.commit()
        conn.close()

        return redirect('/')

    except sqlite3.IntegrityError:
        # Profile already exists
        return redirect('/')
    except Exception as e:
        logger.error(f"Error adding profile: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/delete_profile/<int:profile_id>', methods=['POST'])
def delete_profile(profile_id):
    """Delete profile and all its tweets"""
    try:
        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()

        cursor.execute("DELETE FROM tweets WHERE profile_id = ?", (profile_id,))
        cursor.execute("DELETE FROM scrape_logs WHERE profile_id = ?", (profile_id,))
        cursor.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))

        conn.commit()
        conn.close()

        return jsonify({"message": "Profile deleted successfully"})

    except Exception as e:
        logger.error(f"Error deleting profile: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/scrape_now/<username>', methods=['POST'])
def scrape_now(username):
    """
    Trigger async scraping for a profile.
    Returns immediately with task ID.
    """
    try:
        # Queue scraping task
        task = scrape_profile_task.delay(username)

        logger.info(f"Scraping queued for @{username}, task_id={task.id}")

        return jsonify({
            "message": f"Scraping queued for @{username}",
            "task_id": task.id,
            "status": "queued"
        })

    except Exception as e:
        logger.error(f"Error queueing scrape: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/tweets/<username>')
def view_tweets(username):
    """View tweets for a specific profile"""
    try:
        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT tweet_text, tweet_url, language, likes, retweets, replies,
                   is_retweet, original_author, scraped_date
            FROM tweets t
            JOIN profiles p ON t.profile_id = p.id
            WHERE p.username = ?
            ORDER BY t.scraped_date DESC
        """, (username,))

        tweets = []
        for row in cursor.fetchall():
            tweets.append({
                'tweet_text': row[0],
                'tweet_url': row[1],
                'language': row[2] or 'unknown',
                'likes': row[3],
                'retweets': row[4],
                'replies': row[5],
                'is_retweet': bool(row[6]) if row[6] is not None else False,
                'original_author': row[7],
                'scraped_date': row[8]
            })

        conn.close()

        return render_template('tweets.html', username=username, tweets=tweets)

    except Exception as e:
        logger.error(f"Error loading tweets: {e}")
        return f"Error: {e}", 500


@bp.route('/search')
def search():
    """Search tweets"""
    query = request.args.get('q', '').strip()
    author = request.args.get('author', '').strip()
    lang = request.args.get('lang', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    sort = request.args.get('sort', 'date')

    try:
        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()

        # Get all profiles for filter
        cursor.execute("SELECT DISTINCT username FROM profiles ORDER BY username")
        profiles = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT COUNT(*) FROM tweets")
        total_tweets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM profiles")
        total_profiles = cursor.fetchone()[0]

        results = []
        searched = bool(query or author or lang or date_from or date_to)

        if searched:
            sql = """
                SELECT tweet_text, tweet_url, author, language,
                       likes, retweets, replies, scraped_date, is_retweet, original_author
                FROM tweets
                WHERE 1=1
            """
            params = []

            if query:
                sql += " AND tweet_text LIKE ?"
                params.append(f'%{query}%')

            if author:
                sql += " AND author = ?"
                params.append(author)

            if lang:
                sql += " AND language = ?"
                params.append(lang)

            if date_from:
                sql += " AND DATE(scraped_date) >= ?"
                params.append(date_from)

            if date_to:
                sql += " AND DATE(scraped_date) <= ?"
                params.append(date_to)

            if sort == 'date':
                sql += " ORDER BY scraped_date DESC"
            elif sort == 'likes':
                sql += " ORDER BY likes DESC"
            else:
                sql += " ORDER BY scraped_date DESC"

            sql += " LIMIT 100"

            cursor.execute(sql, params)

            import re
            for row in cursor.fetchall():
                tweet_text = row[0]

                highlighted = tweet_text
                if query:
                    terms = query.split()
                    for term in terms:
                        if term:
                            pattern = re.compile(f'({re.escape(term)})', re.IGNORECASE)
                            highlighted = pattern.sub(r'<span class="highlight">\1</span>', highlighted)

                results.append({
                    'tweet_text': tweet_text,
                    'highlighted_text': highlighted,
                    'tweet_url': row[1],
                    'author': row[2],
                    'language': row[3] or 'unknown',
                    'likes': row[4],
                    'retweets': row[5],
                    'replies': row[6],
                    'scraped_date': row[7],
                    'is_retweet': bool(row[8]) if row[8] is not None else False,
                    'original_author': row[9]
                })

        conn.close()

        return render_template(
            'search.html',
            query=query,
            author=author,
            lang=lang,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            results=results,
            searched=searched,
            profiles=profiles,
            total_tweets=total_tweets,
            total_profiles=total_profiles
        )

    except Exception as e:
        logger.error(f"Error searching: {e}")
        return f"Error: {e}", 500


@bp.route('/monitoring')
def monitoring():
    """Monitoring dashboard with pool stats and task queue"""
    from app.services.driver_pool import get_driver_pool
    from celery.result import AsyncResult
    from celery_app.celery_config import celery_app

    try:
        # Get driver pool stats
        pool = get_driver_pool()
        pool_stats = pool.get_stats()

        # Get Celery stats
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active() or {}
        scheduled_tasks = inspect.scheduled() or {}
        reserved_tasks = inspect.reserved() or {}

        return render_template(
            'monitoring.html',
            pool_stats=pool_stats,
            active_tasks=active_tasks,
            scheduled_tasks=scheduled_tasks,
            reserved_tasks=reserved_tasks
        )

    except Exception as e:
        logger.error(f"Error loading monitoring: {e}")
        return f"Error: {e}", 500

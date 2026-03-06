"""
Brave Story Maker — Application Entry Point
─────────────────────────────────────────────
Configures Flask, registers Blueprints, sets up rate limiting,
and serves the single-page client application.
"""

import os
import sys
import time
from pathlib import Path

from flask import Flask, request, send_from_directory, Response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

BUILD_TS = str(int(time.time()))  # unique on every server restart

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / '.env')

# Add server dir to path for local imports
sys.path.insert(0, os.path.dirname(__file__))

# Database (PostgreSQL + SQLite fallback)
import database_v2 as db

# Logging
from monitoring import setup_logging, log_request, log_response
from cloud_storage import create_storage

# Blueprints
from routes.auth import auth_bp
from routes.stories import stories_bp, init_stories_bp
from routes.health import health_bp, init_health_bp
from routes.credits import credits_bp

import logging
setup_logging()
logger = logging.getLogger('brave_story.app')

# ── App factory ───────────────────────────────────────────────────────

app = Flask(__name__, static_folder=None)

# ── CORS: restrict to explicit origins (never wildcard in production) ─
_allowed_origins = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5000,http://127.0.0.1:5000'
)
CORS(app, origins=[o.strip() for o in _allowed_origins.split(',')],
     supports_credentials=False)

# ── Rate limiting (in-memory; swap to Redis for multi-process) ───────
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "60 per hour"],
    storage_uri="memory://",
)
# Tighter limits on sensitive endpoints
limiter.limit("10 per minute")(auth_bp)
limiter.limit("5 per minute")(stories_bp)

# ── Register Blueprints ──────────────────────────────────────────────
app.register_blueprint(auth_bp)
app.register_blueprint(stories_bp)
app.register_blueprint(health_bp)
app.register_blueprint(credits_bp)

# ── Request / response logging ───────────────────────────────────────

@app.before_request
def before_req():
    """Start a request timer for performance logging."""
    log_request()

@app.after_request
def after_req(response):
    """Log method, path, status, and duration of every request."""
    return log_response(response)

@app.after_request
def add_no_cache(response):
    """Prevent browsers from caching API responses."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.after_request
def add_security_headers(response):
    """Add OWASP-recommended security headers to every response."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response


# ── Helpers ───────────────────────────────────────────────────────────

def serve_html(filename):
    """Serve an HTML file with cache-busted asset URLs."""
    html = (CLIENT_DIR / filename).read_text(encoding='utf-8')
    html = html.replace('/css/styles.css"', f'/css/styles.css?v={BUILD_TS}"')
    html = html.replace('/css/dashboard.css"', f'/css/dashboard.css?v={BUILD_TS}"')
    html = html.replace('/js/home.js"',   f'/js/home.js?v={BUILD_TS}"')
    html = html.replace('/js/create.js"', f'/js/create.js?v={BUILD_TS}"')
    html = html.replace('/js/story.js"',  f'/js/story.js?v={BUILD_TS}"')
    html = html.replace('/js/auth.js"',   f'/js/auth.js?v={BUILD_TS}"')
    html = html.replace('/js/nav-profile.js"', f'/js/nav-profile.js?v={BUILD_TS}"')
    html = html.replace('/js/admin-credits.js"', f'/js/admin-credits.js?v={BUILD_TS}"')
    html = html.replace('/js/my-credits.js"', f'/js/my-credits.js?v={BUILD_TS}"')
    return Response(html, mimetype='text/html')


# ── Init DB on startup ───────────────────────────────────────────────
db.init_db()

# Static dirs
CLIENT_DIR = Path(__file__).parent.parent / 'client'
IMAGES_DIR = CLIENT_DIR / 'generated_images'
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Initialize cloud storage and inject into blueprints
image_storage = create_storage(str(IMAGES_DIR))
init_stories_bp(image_storage)
init_health_bp(image_storage)

# ── Static file serving ──────────────────────────────────────────────

@app.route('/')
def serve_index():
    """Serve the main landing page."""
    return serve_html('index.html')

@app.route('/create')
def serve_create():
    """Serve the story creation page."""
    return serve_html('create.html')

@app.route('/login')
def serve_login():
    """Serve the login / registration page."""
    return serve_html('login.html')

@app.route('/story/<int:story_id>')
def serve_story(story_id):
    """Serve the story reader page."""
    return serve_html('story.html')

@app.route('/admin-credits')
def serve_admin_credits():
    """Serve the admin credit dashboard."""
    return serve_html('admin-credits.html')

@app.route('/my-credits')
def serve_my_credits():
    """Serve the user credit dashboard."""
    return serve_html('my-credits.html')

@app.route('/css/<path:filename>')
def serve_css(filename):
    """Serve CSS assets from the client directory."""
    return send_from_directory(CLIENT_DIR / 'css', filename)

@app.route('/js/<path:filename>')
def serve_js(filename):
    """Serve JavaScript assets from the client directory."""
    return send_from_directory(CLIENT_DIR / 'js', filename)

@app.route('/generated_images/<path:filename>')
def serve_image(filename):
    """Serve generated story images."""
    return send_from_directory(IMAGES_DIR, filename)


# ── Entry point ───────────────────────────────────────────────────────

if __name__ == '__main__':
    logger.info('🚀 Brave Story Maker server starting...')
    logger.info(f'📂 Serving client from: {CLIENT_DIR}')
    logger.info(f'💾 Storage backend: {image_storage.__class__.__name__}')
    app.run(host='0.0.0.0', port=5002, debug=True)

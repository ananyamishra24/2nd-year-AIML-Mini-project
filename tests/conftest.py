"""
Shared test fixtures for Brave Story Maker.
"""

import os
import sys
import tempfile
import pytest

# Ensure the server package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

# Force SQLite (in-memory or temp file) for all tests
os.environ.pop('DATABASE_URL', None)

# Force local storage so tests don't require boto3 / azure
os.environ['STORAGE_BACKEND'] = 'local'
os.environ.pop('AWS_S3_BUCKET', None)
os.environ.pop('AZURE_STORAGE_CONNECTION_STRING', None)


@pytest.fixture()
def app(tmp_path):
    """Create a fresh Flask app for each test with a clean DB."""
    # Point SQLite at a temp file so each test gets an isolated database
    import database_v2 as db
    db.DB_PATH = str(tmp_path / 'test.db')

    # Import after env is set so database_v2 picks SQLite
    from main import app as flask_app

    flask_app.config['TESTING'] = True

    # Initialise a clean database for the test
    db.init_db()

    yield flask_app


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def auth_header(client):
    """Register a test user and return an Authorization header with a valid JWT."""
    resp = client.post('/api/auth/register', json={
        'email': 'test@example.com',
        'name': 'Test User',
        'password': 'securepassword123',
    })
    token = resp.get_json()['token']
    return {'Authorization': f'Bearer {token}'}

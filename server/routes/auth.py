"""
Authentication Routes Blueprint
────────────────────────────────
Handles user registration, login, profile retrieval, and account management.
"""

import os
import logging
from flask import Blueprint, request, jsonify, g

import database_v2 as db
from auth import (
    hash_password, verify_password, create_token,
    validate_registration, login_required,
)
from content_safety import sanitize_html

try:
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests
    _GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    _GOOGLE_AUTH_AVAILABLE = False

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')

logger = logging.getLogger('brave_story.routes.auth')

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user account.

    Expects JSON body with ``email``, ``name``, and ``password``.
    Returns the created user object and a JWT token.
    """
    data = request.get_json()
    valid, error = validate_registration(data)
    if not valid:
        return jsonify({'message': error}), 400

    existing = db.get_user_by_email(data['email'])
    if existing:
        return jsonify({'message': 'Email already registered'}), 409

    pw_hash, salt = hash_password(data['password'])
    user = db.create_user(data['email'], sanitize_html(data['name']), pw_hash, salt)
    if not user:
        return jsonify({'message': 'Failed to create user'}), 500

    token = create_token(user['id'], data['email'])
    logger.info(f'New user registered: {data["email"]}')
    return jsonify({'user': user, 'token': token}), 201


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """Authenticate a user and return a JWT token.

    Expects JSON body with ``email`` and ``password``.
    """
    data = request.get_json()
    user_row = db.get_user_by_email(data.get('email', ''))
    if not user_row:
        return jsonify({'message': 'Invalid email or password'}), 401

    if not verify_password(data.get('password', ''), user_row['password_hash'], user_row['salt']):
        return jsonify({'message': 'Invalid email or password'}), 401

    db.update_last_login(user_row['id'])
    token = create_token(user_row['id'], data['email'])
    user = db.get_user_by_id(user_row['id'])
    logger.info(f'User logged in: {data["email"]}')
    return jsonify({'user': user, 'token': token})


@auth_bp.route('/api/auth/me', methods=['GET'])
@login_required
def get_profile():
    """Return the authenticated user's profile.

    Requires a valid JWT in the ``Authorization`` header.
    """
    user = db.get_user_by_id(g.user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify(user)


@auth_bp.route('/api/auth/profile', methods=['PATCH'])
@login_required
def update_profile():
    """Update the authenticated user's display name."""
    data = request.get_json() or {}
    name = sanitize_html((data.get('name') or '').strip())
    if not name or len(name) < 2:
        return jsonify({'message': 'Name must be at least 2 characters'}), 400
    if len(name) > 100:
        return jsonify({'message': 'Name is too long (max 100 characters)'}), 400

    user = db.update_user_name(g.user_id, name)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    logger.info(f'User {g.user_id} updated display name')
    return jsonify({'user': user})


@auth_bp.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password():
    """Change the authenticated user's password.

    Expects JSON with ``current_password`` and ``new_password``.
    """
    data = request.get_json() or {}
    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')

    if not current_pw or not new_pw:
        return jsonify({'message': 'Both current and new password are required'}), 400
    if len(new_pw) < 8:
        return jsonify({'message': 'New password must be at least 8 characters'}), 400

    user_row = db.get_user_by_email(g.user_email)
    if not user_row:
        return jsonify({'message': 'User not found'}), 404
    if not verify_password(current_pw, user_row['password_hash'], user_row['salt']):
        return jsonify({'message': 'Current password is incorrect'}), 401

    pw_hash, salt = hash_password(new_pw)
    db.update_user_password(g.user_id, pw_hash, salt)
    logger.info(f'User {g.user_id} changed password')
    return jsonify({'message': 'Password updated successfully'})


@auth_bp.route('/api/auth/google/config', methods=['GET'])
def google_config():
    """Return the Google OAuth client ID for the frontend (not a secret)."""
    return jsonify({'client_id': GOOGLE_CLIENT_ID})


@auth_bp.route('/api/auth/google', methods=['POST'])
def google_login():
    """Verify a Google ID token and return a Cartoon Care JWT.

    Expects JSON with ``credential`` (the Google ID token string).
    Creates the user account if first-time, or links Google to an existing
    email/password account automatically.
    """
    if not _GOOGLE_AUTH_AVAILABLE:
        return jsonify({'message': 'Google login is not available'}), 503
    if not GOOGLE_CLIENT_ID:
        return jsonify({'message': 'Google login is not configured'}), 503

    data = request.get_json() or {}
    credential = data.get('credential', '').strip()
    if not credential:
        return jsonify({'message': 'Google credential is required'}), 400

    # Verify the Google ID token
    try:
        idinfo = google_id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        logger.warning(f'Invalid Google token: {exc}')
        return jsonify({'message': 'Invalid Google credential'}), 401

    google_id = idinfo['sub']
    email = idinfo.get('email', '')
    name = sanitize_html(idinfo.get('name', '') or email.split('@')[0])
    email_verified = idinfo.get('email_verified', False)

    if not email or not email_verified:
        return jsonify({'message': 'Google account email is not verified'}), 400

    # 1. Check if we already know this Google account
    existing = db.get_user_by_google_id(google_id)
    if existing:
        user = db.get_user_by_id(existing['id'])
        db.update_last_login(existing['id'])
        token = create_token(existing['id'], email)
        logger.info(f'Google login (existing google_id): {email}')
        return jsonify({'user': user, 'token': token})

    # 2. Email already registered with a password account — link Google to it
    email_user = db.get_user_by_email(email)
    if email_user:
        db.link_google_id(email_user['id'], google_id)
        db.update_last_login(email_user['id'])
        user = db.get_user_by_id(email_user['id'])
        token = create_token(email_user['id'], email)
        logger.info(f'Google login (linked to existing account): {email}')
        return jsonify({'user': user, 'token': token})

    # 3. Brand-new user — create Google account
    user = db.create_google_user(email, name, google_id)
    if not user:
        return jsonify({'message': 'Failed to create account'}), 500
    db.update_last_login(user['id'])
    token = create_token(user['id'], email)
    logger.info(f'Google login (new user): {email}')
    return jsonify({'user': user, 'token': token}), 201


@auth_bp.route('/api/auth/account', methods=['DELETE'])
@login_required
def delete_account():
    """Permanently delete the authenticated user's account.

    Expects JSON with ``password`` for confirmation.
    """
    data = request.get_json() or {}
    password = data.get('password', '')

    if not password:
        return jsonify({'message': 'Password confirmation required'}), 400

    user_row = db.get_user_by_email(g.user_email)
    if not user_row:
        return jsonify({'message': 'User not found'}), 404
    if not verify_password(password, user_row['password_hash'], user_row['salt']):
        return jsonify({'message': 'Incorrect password'}), 401

    db.delete_user(g.user_id)
    logger.info(f'User {g.user_id} deleted their account')
    return jsonify({'message': 'Account deleted successfully'})

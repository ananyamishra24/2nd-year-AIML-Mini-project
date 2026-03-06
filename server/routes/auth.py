"""
Authentication Routes Blueprint
────────────────────────────────
Handles user registration, login, and profile retrieval.
"""

import logging
from flask import Blueprint, request, jsonify, g

import database_v2 as db
from auth import (
    hash_password, verify_password, create_token,
    validate_registration, login_required,
)
from content_safety import sanitize_html

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

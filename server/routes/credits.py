"""
Credit Usage Monitoring Routes
──────────────────────────────
Admin and user credit dashboards with Flux 2 Pro tracking.
"""

import logging
from flask import Blueprint, request, jsonify, g

import database_v2 as db
from auth import login_required

logger = logging.getLogger('brave_story.credits')

credits_bp = Blueprint('credits', __name__)


# ── Admin middleware ────────────────────────────────────────────────

def admin_required(f):
    """Decorator: require admin privileges (stacks with @login_required)."""
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not db.is_user_admin(g.user_id):
            return jsonify({'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════════════════
#  ADMIN CREDIT ROUTES
# ══════════════════════════════════════════════════════════════════════

@credits_bp.route('/api/admin/credits/overview', methods=['GET'])
@admin_required
def admin_credit_overview():
    """Full credit overview: totals, balance, per-API breakdown."""
    config = db.get_credit_config()
    usage = db.get_total_credits_used()
    total_budget = float(config.get('total_budget', '1000'))
    grand_total = usage.get('grand_total', 0)
    remaining = total_budget - grand_total

    return jsonify({
        'total_budget': total_budget,
        'total_used': grand_total,
        'remaining': remaining,
        'usage_percent': round((grand_total / total_budget * 100) if total_budget > 0 else 0, 2),
        'by_api': usage.get('by_api', {}),
        'cost_config': {
            'flux2pro_cost_per_image': float(config.get('flux2pro_cost_per_image', '0.05')),
            'claude_cost_per_call': float(config.get('claude_cost_per_call', '0.01')),
        }
    })


@credits_bp.route('/api/admin/credits/history', methods=['GET'])
@admin_required
def admin_credit_history():
    """Daily credit usage history (default 30 days)."""
    days = request.args.get('days', 30, type=int)
    history = db.get_credit_usage_history(days)
    return jsonify({'history': history, 'days': days})


@credits_bp.route('/api/admin/credits/by-user', methods=['GET'])
@admin_required
def admin_credit_by_user():
    """Credit usage breakdown by user."""
    users = db.get_credit_usage_by_user()
    return jsonify({'users': users})


@credits_bp.route('/api/admin/credits/hourly', methods=['GET'])
@admin_required
def admin_credit_hourly():
    """Hourly usage breakdown for today."""
    hourly = db.get_hourly_usage_today()
    return jsonify({'hourly': hourly})


@credits_bp.route('/api/admin/credits/config', methods=['GET'])
@admin_required
def admin_get_config():
    """Get credit configuration."""
    config = db.get_credit_config()
    return jsonify(config)


@credits_bp.route('/api/admin/credits/config', methods=['PUT'])
@admin_required
def admin_update_config():
    """Update credit configuration."""
    data = request.get_json()
    allowed_keys = {'total_budget', 'flux2pro_cost_per_image', 'claude_cost_per_call'}
    updated = []
    for key, value in data.items():
        if key in allowed_keys:
            db.set_credit_config(key, str(value))
            updated.append(key)
    logger.info(f'Admin {g.user_email} updated credit config: {updated}')
    return jsonify({'success': True, 'updated': updated})


@credits_bp.route('/api/admin/credits/users', methods=['GET'])
@admin_required
def admin_all_users():
    """List all users with their credit usage summary."""
    users = db.get_all_users_summary()
    return jsonify({'users': users})


@credits_bp.route('/api/admin/users/<int:user_id>/set-admin', methods=['POST'])
@admin_required
def admin_set_admin(user_id):
    """Grant or revoke admin status for a user."""
    data = request.get_json()
    is_admin = data.get('is_admin', False)
    db.set_user_admin(user_id, is_admin)
    logger.info(f'Admin {g.user_email} set user {user_id} admin={is_admin}')
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════════════
#  USER CREDIT ROUTES
# ══════════════════════════════════════════════════════════════════════

@credits_bp.route('/api/credits/my', methods=['GET'])
@login_required
def user_credit_overview():
    """Get the logged-in user's credit usage overview."""
    usage = db.get_user_credit_usage(g.user_id)
    return jsonify({
        'total_used': usage.get('grand_total', 0),
        'by_api': usage.get('by_api', {}),
    })


@credits_bp.route('/api/credits/my/history', methods=['GET'])
@login_required
def user_credit_history():
    """Get the logged-in user's daily credit history."""
    days = request.args.get('days', 30, type=int)
    history = db.get_user_credit_history(g.user_id, days)
    return jsonify({'history': history, 'days': days})


@credits_bp.route('/api/credits/my/stories', methods=['GET'])
@login_required
def user_story_credits():
    """Get per-story credit breakdown for the logged-in user."""
    limit = request.args.get('limit', 20, type=int)
    stories = db.get_user_story_credits(g.user_id, limit)
    return jsonify({'stories': stories})

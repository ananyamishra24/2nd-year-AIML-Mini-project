"""
Database Layer (PostgreSQL + SQLite fallback)
─────────────────────────────────────────────
Supports PostgreSQL for production and SQLite for local development.
Includes: users, children profiles, stories, personalization preferences.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List
from contextlib import contextmanager

logger = logging.getLogger('brave_story.database')

# ── Determine database backend ───────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '')
USE_POSTGRES = DATABASE_URL.startswith('postgres')

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    logger.info(f'Using PostgreSQL: {DATABASE_URL[:30]}...')
else:
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'stories.db')
    logger.info(f'Using SQLite: {DB_PATH}')


# ── Connection management ────────────────────────────────────────────

@contextmanager
def get_db():
    """Get a database connection (PostgreSQL or SQLite)."""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _execute(conn, sql, params=None):
    """Execute SQL, translating placeholders for the active backend."""
    if USE_POSTGRES:
        # Convert ? to %s for psycopg2
        sql = sql.replace('?', '%s')
        # Convert AUTOINCREMENT to SERIAL
        sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
        sql = sql.replace("datetime('now')", "NOW()")
    cur = conn.cursor()
    cur.execute(sql, params or ())
    return cur


def _fetchone(conn, sql, params=None):
    cur = _execute(conn, sql, params)
    if USE_POSTGRES:
        cols = [desc[0] for desc in cur.description] if cur.description else []
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    else:
        return cur.fetchone()


def _fetchall(conn, sql, params=None):
    cur = _execute(conn, sql, params)
    if USE_POSTGRES:
        cols = [desc[0] for desc in cur.description] if cur.description else []
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    else:
        return cur.fetchall()


# ── Schema initialization ────────────────────────────────────────────

def init_db():
    """Create all tables."""
    with get_db() as conn:
        # Users table
        _execute(conn, '''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                last_login TEXT
            )
        ''')

        # Children profiles (linked to parent user)
        _execute(conn, '''
            CREATE TABLE IF NOT EXISTS children (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL DEFAULT 'neutral',
                conditions TEXT DEFAULT '[]',
                preferences TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        # Stories table (extended with user_id)
        _execute(conn, '''
            CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                child_id INTEGER,
                child_name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                condition TEXT NOT NULL,
                hero_characteristics TEXT,
                story_title TEXT,
                pages TEXT NOT NULL DEFAULT '[]',
                is_favorite INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                moderation_flags TEXT DEFAULT '[]',
                generation_time_ms INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (child_id) REFERENCES children(id) ON DELETE SET NULL
            )
        ''')

        # Personalization preferences (learning over time)
        _execute(conn, '''
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_id INTEGER NOT NULL,
                preference_type TEXT NOT NULL,
                preference_value TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (child_id) REFERENCES children(id) ON DELETE CASCADE
            )
        ''')

        # Story feedback (for personalization learning)
        _execute(conn, '''
            CREATE TABLE IF NOT EXISTS story_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_id INTEGER NOT NULL,
                child_id INTEGER,
                rating INTEGER,
                favorite_page INTEGER,
                read_count INTEGER DEFAULT 1,
                total_read_time_sec INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE CASCADE,
                FOREIGN KEY (child_id) REFERENCES children(id) ON DELETE SET NULL
            )
        ''')

        # API usage log table
        _execute(conn, '''
            CREATE TABLE IF NOT EXISTS api_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_name TEXT NOT NULL,
                model TEXT,
                success INTEGER NOT NULL DEFAULT 1,
                duration_ms INTEGER,
                tokens_used INTEGER DEFAULT 0,
                error_message TEXT,
                user_id INTEGER,
                story_id INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
        ''')

        # ── Migrations: add missing columns to existing SQLite tables ──
        if not USE_POSTGRES:
            migrations = [
                ('stories', 'user_id',              'INTEGER'),
                ('stories', 'child_id',             'INTEGER'),
                ('stories', 'hero_characteristics',  'TEXT'),
                ('stories', 'moderation_flags',     "TEXT DEFAULT '[]'"),
                ('stories', 'generation_time_ms',   'INTEGER DEFAULT 0'),
                ('api_logs', 'user_id',             'INTEGER'),
                ('api_logs', 'story_id',            'INTEGER'),
            ]
            cur = conn.cursor()
            for table, column, col_def in migrations:
                cur.execute(f'PRAGMA table_info({table})')
                existing = [row[1] for row in cur.fetchall()]
                if column not in existing:
                    cur.execute(f'ALTER TABLE {table} ADD COLUMN {column} {col_def}')
                    logger.info(f'Migration: added column {table}.{column}')

    logger.info('Database initialized successfully')


# ── Row converters ───────────────────────────────────────────────────

def _row_to_dict(row) -> Optional[dict]:
    """Convert a row to a dict (works for both SQLite Row and PG dict)."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)


def row_to_story(row) -> Optional[dict]:
    d = _row_to_dict(row)
    if d is None:
        return None
    d['pages'] = json.loads(d['pages']) if isinstance(d['pages'], str) else d['pages']
    d['isFavorite'] = bool(d.pop('is_favorite', 0))
    d['childName'] = d.pop('child_name', '')
    d['heroCharacteristics'] = d.pop('hero_characteristics', '') or ''
    d['storyTitle'] = d.pop('story_title', '') or ''
    d['createdAt'] = d.pop('created_at', '') or ''
    d.pop('moderation_flags', None)
    d.pop('generation_time_ms', None)
    return d


def row_to_user(row) -> Optional[dict]:
    d = _row_to_dict(row)
    if d is None:
        return None
    d.pop('password_hash', None)
    d.pop('salt', None)
    d['createdAt'] = d.pop('created_at', '') or ''
    d['lastLogin'] = d.pop('last_login', '') or ''
    return d


def row_to_child(row) -> Optional[dict]:
    d = _row_to_dict(row)
    if d is None:
        return None
    d['conditions'] = json.loads(d['conditions']) if isinstance(d['conditions'], str) else d['conditions']
    d['preferences'] = json.loads(d['preferences']) if isinstance(d['preferences'], str) else d['preferences']
    d['createdAt'] = d.pop('created_at', '') or ''
    d.pop('user_id', None)
    return d


# ── User operations ──────────────────────────────────────────────────

def create_user(email: str, name: str, password_hash: str, salt: str) -> Optional[dict]:
    with get_db() as conn:
        _execute(conn,
            'INSERT INTO users (email, name, password_hash, salt) VALUES (?, ?, ?, ?)',
            (email, name, password_hash, salt)
        )
        row = _fetchone(conn, 'SELECT * FROM users WHERE email = ?', (email,))
        return row_to_user(row)


def get_user_by_email(email: str) -> Optional[dict]:
    with get_db() as conn:
        row = _fetchone(conn, 'SELECT * FROM users WHERE email = ?', (email,))
        return _row_to_dict(row)


def get_user_by_id(user_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = _fetchone(conn, 'SELECT * FROM users WHERE id = ?', (user_id,))
        return row_to_user(row)  # type: ignore[return-value]


def update_last_login(user_id: int):
    with get_db() as conn:
        now = datetime.now(timezone.utc).isoformat()
        _execute(conn, 'UPDATE users SET last_login = ? WHERE id = ?', (now, user_id))


# ── Children profile operations ──────────────────────────────────────

def create_child(user_id: int, name: str, age: int, gender: str,
                 conditions: Optional[list] = None) -> Optional[dict]:
    with get_db() as conn:
        _execute(conn,
            'INSERT INTO children (user_id, name, age, gender, conditions) VALUES (?, ?, ?, ?, ?)',
            (user_id, name, age, gender, json.dumps(conditions or []))
        )
        rows = _fetchall(conn,
            'SELECT * FROM children WHERE user_id = ? ORDER BY id DESC LIMIT 1',
            (user_id,)
        )
        return row_to_child(rows[0]) if rows else None  # type: ignore[return-value]


def get_children(user_id: int) -> list:
    with get_db() as conn:
        rows = _fetchall(conn,
            'SELECT * FROM children WHERE user_id = ? ORDER BY name',
            (user_id,)
        )
        return [row_to_child(r) for r in rows]


def get_child(child_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = _fetchone(conn, 'SELECT * FROM children WHERE id = ?', (child_id,))
        return row_to_child(row) if row else None


def update_child(child_id: int, **kwargs) -> Optional[dict]:
    allowed = {'name', 'age', 'gender', 'conditions', 'preferences'}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_child(child_id)

    if 'conditions' in updates:
        updates['conditions'] = json.dumps(updates['conditions'])
    if 'preferences' in updates:
        updates['preferences'] = json.dumps(updates['preferences'])

    with get_db() as conn:
        set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
        values = list(updates.values()) + [child_id]
        _execute(conn, f'UPDATE children SET {set_clause} WHERE id = ?', values)
        row = _fetchone(conn, 'SELECT * FROM children WHERE id = ?', (child_id,))
        return row_to_child(row) if row else None


def delete_child(child_id: int) -> bool:
    with get_db() as conn:
        cur = _execute(conn, 'DELETE FROM children WHERE id = ?', (child_id,))
        return cur.rowcount > 0


# ── Story operations (extended) ──────────────────────────────────────

def create_story(child_name: str, age: int, gender: str, condition: str,
                 hero_characteristics: str, story_title: str, pages: list,
                 user_id: Optional[int] = None, child_id: Optional[int] = None,
                 moderation_flags: Optional[list] = None, generation_time_ms: int = 0) -> Optional[dict]:
    with get_db() as conn:
        _execute(conn,
            '''INSERT INTO stories (user_id, child_id, child_name, age, gender, condition,
               hero_characteristics, story_title, pages, moderation_flags, generation_time_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, child_id, child_name, age, gender, condition,
             hero_characteristics, story_title, json.dumps(pages),
             json.dumps(moderation_flags or []), generation_time_ms)
        )
        # Get the newly created story
        rows = _fetchall(conn, 'SELECT * FROM stories ORDER BY id DESC LIMIT 1')
        return row_to_story(rows[0]) if rows else None


def get_story(story_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = _fetchone(conn, 'SELECT * FROM stories WHERE id = ?', (story_id,))
        return row_to_story(row) if row else None


def get_stories(user_id: Optional[int] = None) -> list:
    with get_db() as conn:
        if user_id:
            rows = _fetchall(conn,
                'SELECT * FROM stories WHERE user_id = ? ORDER BY id DESC',
                (user_id,)
            )
        else:
            rows = _fetchall(conn, 'SELECT * FROM stories ORDER BY id DESC')
        return [row_to_story(r) for r in rows]


def get_favorite_stories(user_id: Optional[int] = None) -> list:
    with get_db() as conn:
        if user_id:
            rows = _fetchall(conn,
                'SELECT * FROM stories WHERE is_favorite = 1 AND user_id = ? ORDER BY id DESC',
                (user_id,)
            )
        else:
            rows = _fetchall(conn,
                'SELECT * FROM stories WHERE is_favorite = 1 ORDER BY id DESC'
            )
        return [row_to_story(r) for r in rows]


def toggle_favorite(story_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = _fetchone(conn, 'SELECT * FROM stories WHERE id = ?', (story_id,))
        if not row:
            return None
        d = _row_to_dict(row)
        if d is None:
            return None
        new_val = 0 if d.get('is_favorite') else 1
        _execute(conn, 'UPDATE stories SET is_favorite = ? WHERE id = ?', (new_val, story_id))
        row = _fetchone(conn, 'SELECT * FROM stories WHERE id = ?', (story_id,))
        return row_to_story(row)


def delete_story(story_id: int) -> bool:
    with get_db() as conn:
        cur = _execute(conn, 'DELETE FROM stories WHERE id = ?', (story_id,))
        return cur.rowcount > 0


# ── Personalization operations ───────────────────────────────────────

def add_preference(child_id: int, pref_type: str, pref_value: str,
                   weight: float = 1.0) -> Optional[dict]:
    with get_db() as conn:
        _execute(conn,
            'INSERT INTO preferences (child_id, preference_type, preference_value, weight) VALUES (?, ?, ?, ?)',
            (child_id, pref_type, pref_value, weight)
        )
        rows = _fetchall(conn,
            'SELECT * FROM preferences WHERE child_id = ? ORDER BY id DESC LIMIT 1',
            (child_id,)
        )
        return _row_to_dict(rows[0]) if rows else None


def get_preferences(child_id: int) -> list:
    with get_db() as conn:
        rows = _fetchall(conn,
            '''SELECT preference_type, preference_value,
                      SUM(weight) as total_weight, COUNT(*) as count
               FROM preferences WHERE child_id = ?
               GROUP BY preference_type, preference_value
               ORDER BY total_weight DESC''',
            (child_id,)
        )
        return [_row_to_dict(r) for r in rows]


def record_story_feedback(story_id: int, child_id: Optional[int] = None,
                          rating: Optional[int] = None, favorite_page: Optional[int] = None,
                          read_time_sec: int = 0):
    with get_db() as conn:
        existing = _fetchone(conn,
            'SELECT * FROM story_feedback WHERE story_id = ?',
            (story_id,)
        )
        if existing:
            d = _row_to_dict(existing)
            _execute(conn,
                '''UPDATE story_feedback SET
                   read_count = read_count + 1,
                   total_read_time_sec = total_read_time_sec + ?,
                   rating = COALESCE(?, rating),
                   favorite_page = COALESCE(?, favorite_page)
                   WHERE story_id = ?''',
                (read_time_sec, rating, favorite_page, story_id)
            )
        else:
            _execute(conn,
                '''INSERT INTO story_feedback
                   (story_id, child_id, rating, favorite_page, total_read_time_sec)
                   VALUES (?, ?, ?, ?, ?)''',
                (story_id, child_id, rating, favorite_page, read_time_sec)
            )


def get_child_story_history(child_id: int) -> list:
    """Get story history with feedback for a child — used for personalization."""
    with get_db() as conn:
        rows = _fetchall(conn,
            '''SELECT s.*, sf.rating, sf.read_count, sf.favorite_page, sf.total_read_time_sec
               FROM stories s
               LEFT JOIN story_feedback sf ON s.id = sf.story_id
               WHERE s.child_id = ?
               ORDER BY s.id DESC
               LIMIT 20''',
            (child_id,)
        )
        return [_row_to_dict(r) for r in rows]


# ── API log operations ───────────────────────────────────────────────

def log_api_call(api_name: str, model: str = '', success: bool = True,
                 duration_ms: int = 0, tokens_used: int = 0,
                 error_message: str = '', user_id: Optional[int] = None,
                 story_id: Optional[int] = None):
    try:
        with get_db() as conn:
            _execute(conn,
                '''INSERT INTO api_logs
                   (api_name, model, success, duration_ms, tokens_used,
                    error_message, user_id, story_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (api_name, model, int(success), duration_ms, tokens_used,
                 error_message, user_id, story_id)
            )
    except Exception as e:
        logger.error(f'Failed to log API call: {e}')


def get_api_usage_stats(days: int = 7) -> list:
    with get_db() as conn:
        rows = _fetchall(conn,
            '''SELECT api_name, COUNT(*) as total_calls,
                      SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                      SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures,
                      AVG(duration_ms) as avg_duration_ms,
                      SUM(tokens_used) as total_tokens
               FROM api_logs
               GROUP BY api_name
               ORDER BY total_calls DESC'''
        )
        return [_row_to_dict(r) for r in rows]

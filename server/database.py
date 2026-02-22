import sqlite3
import json
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'stories.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            condition TEXT NOT NULL,
            hero_characteristics TEXT,
            story_title TEXT,
            pages TEXT NOT NULL DEFAULT '[]',
            is_favorite INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    conn.commit()
    conn.close()


def row_to_story(row) -> dict:
    d = dict(row)
    d['pages'] = json.loads(d['pages'])
    d['isFavorite'] = bool(d.pop('is_favorite'))
    d['childName'] = d.pop('child_name')
    d['heroCharacteristics'] = d.pop('hero_characteristics', '')
    d['storyTitle'] = d.pop('story_title', '')
    d['createdAt'] = d.pop('created_at', '')
    return d


def create_story(child_name: str, age: int, gender: str, condition: str,
                 hero_characteristics: str, story_title: str, pages: list) -> dict:
    conn = get_db()
    cur = conn.execute(
        '''INSERT INTO stories (child_name, age, gender, condition, hero_characteristics,
           story_title, pages) VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (child_name, age, gender, condition, hero_characteristics,
         story_title, json.dumps(pages))
    )
    story_id = cur.lastrowid
    conn.commit()
    row = conn.execute('SELECT * FROM stories WHERE id = ?', (story_id,)).fetchone()
    conn.close()
    return row_to_story(row)


def get_story(story_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute('SELECT * FROM stories WHERE id = ?', (story_id,)).fetchone()
    conn.close()
    return row_to_story(row) if row else None


def get_stories() -> list:
    conn = get_db()
    rows = conn.execute('SELECT * FROM stories ORDER BY id DESC').fetchall()
    conn.close()
    return [row_to_story(r) for r in rows]


def get_favorite_stories() -> list:
    conn = get_db()
    rows = conn.execute('SELECT * FROM stories WHERE is_favorite = 1 ORDER BY id DESC').fetchall()
    conn.close()
    return [row_to_story(r) for r in rows]


def toggle_favorite(story_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute('SELECT * FROM stories WHERE id = ?', (story_id,)).fetchone()
    if not row:
        conn.close()
        return None
    new_val = 0 if row['is_favorite'] else 1
    conn.execute('UPDATE stories SET is_favorite = ? WHERE id = ?', (new_val, story_id))
    conn.commit()
    row = conn.execute('SELECT * FROM stories WHERE id = ?', (story_id,)).fetchone()
    conn.close()
    return row_to_story(row)


def delete_story(story_id: int) -> bool:
    conn = get_db()
    cur = conn.execute('DELETE FROM stories WHERE id = ?', (story_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0

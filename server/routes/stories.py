"""
Story & Children Routes Blueprint
──────────────────────────────────
CRUD for stories and children profiles, story generation,
feedback, and personalization.
"""

import os
import json
import time
import logging

import requests
from flask import Blueprint, request, jsonify, g

import database_v2 as db
from auth import login_required, optional_auth
from content_safety import validate_input, moderate_output, moderate_image_prompt, sanitize_html
from monitoring import usage_counter, AIGenerationTracker
from prompt_manager import build_story_prompt, build_image_prompt

logger = logging.getLogger('brave_story.routes.stories')

stories_bp = Blueprint('stories', __name__)

# cloud storage is injected at registration time via init_app
_image_storage = None


def init_stories_bp(image_storage):
    """Inject the image storage backend so the blueprint can save images."""
    global _image_storage
    _image_storage = image_storage


# ── Children Profile Routes ──────────────────────────────────────────

@stories_bp.route('/api/children', methods=['GET'])
@login_required
def list_children():
    """List all children profiles belonging to the authenticated user."""
    return jsonify(db.get_children(g.user_id))


@stories_bp.route('/api/children', methods=['POST'])
@login_required
def add_child():
    """Create a new child profile.

    Expects JSON with ``name``, ``age``, and optionally ``gender``
    and ``conditions``.  Validates inputs server-side before saving.
    """
    data = request.get_json()

    # ── Server-side input validation ─────────────────────────────
    name = (data.get('name') or '').strip()
    age = data.get('age')
    gender = (data.get('gender') or 'neutral').strip()
    conditions = data.get('conditions', [])

    if not name or len(name) < 1 or len(name) > 50:
        return jsonify({'message': 'Child name must be 1-50 characters'}), 400
    if not isinstance(age, int) or age < 2 or age > 18:
        return jsonify({'message': 'Age must be an integer between 2 and 18'}), 400
    if gender not in ('male', 'female', 'neutral'):
        return jsonify({'message': 'Gender must be male, female, or neutral'}), 400
    if not isinstance(conditions, list) or len(conditions) > 10:
        return jsonify({'message': 'Conditions must be a list (max 10 items)'}), 400
    for c in conditions:
        if not isinstance(c, str) or len(c) > 200:
            return jsonify({'message': 'Each condition must be a string (max 200 chars)'}), 400

    # Sanitize text inputs before storage (XSS prevention)
    name = sanitize_html(name)
    conditions = [sanitize_html(c) for c in conditions]

    child = db.create_child(g.user_id, name, age, gender, conditions)
    return jsonify(child), 201


@stories_bp.route('/api/children/<int:child_id>', methods=['PUT'])
@login_required
def update_child(child_id):
    """Update an existing child profile by ID."""
    data = request.get_json()

    # Sanitize text fields before passing to DB (XSS prevention)
    if 'name' in data and isinstance(data['name'], str):
        data['name'] = sanitize_html(data['name'].strip())
    if 'conditions' in data and isinstance(data['conditions'], list):
        data['conditions'] = [sanitize_html(c) for c in data['conditions'] if isinstance(c, str)]

    child = db.update_child(child_id, **data)
    if not child:
        return jsonify({'message': 'Child not found'}), 404
    return jsonify(child)


@stories_bp.route('/api/children/<int:child_id>', methods=['DELETE'])
@login_required
def delete_child(child_id):
    """Delete a child profile by ID."""
    if not db.delete_child(child_id):
        return jsonify({'message': 'Child not found'}), 404
    return jsonify({'success': True})


# ── Story CRUD Routes ────────────────────────────────────────────────

@stories_bp.route('/api/stories', methods=['GET'])
def list_stories():
    """Return all stories, ordered newest first."""
    return jsonify(db.get_stories())


@stories_bp.route('/api/stories/favorites', methods=['GET'])
def favorite_stories():
    """Return only stories marked as favorite."""
    return jsonify(db.get_favorite_stories())


@stories_bp.route('/api/stories/<int:story_id>', methods=['GET'])
def get_story(story_id):
    """Retrieve a single story by ID."""
    story = db.get_story(story_id)
    if not story:
        return jsonify({'message': 'Story not found'}), 404
    return jsonify(story)


@stories_bp.route('/api/stories/<int:story_id>', methods=['DELETE'])
def delete_story(story_id):
    """Delete a story by ID."""
    deleted = db.delete_story(story_id)
    if not deleted:
        return jsonify({'message': 'Story not found'}), 404
    return jsonify({'success': True, 'message': 'Story deleted successfully'})


@stories_bp.route('/api/stories/<int:story_id>/favorite', methods=['POST'])
def toggle_favorite(story_id):
    """Toggle the favorite flag on a story."""
    story = db.toggle_favorite(story_id)
    if not story:
        return jsonify({'message': 'Story not found'}), 404
    return jsonify(story)


# ── Story Generation ─────────────────────────────────────────────────

@stories_bp.route('/api/stories/generate', methods=['POST'])
@optional_auth
def generate_story():
    """Generate a new story using Gemini + Flux 2 Pro.

    Accepts JSON with ``childName``, ``age``, ``gender``, ``condition``,
    ``heroCharacteristics``, and optional ``childId``.  Validates all
    inputs server-side before AI generation.
    """
    start_time = time.time()
    user_id = getattr(g, 'user_id', None)

    try:
        data = request.get_json()
        child_name = (data.get('childName') or '').strip()
        age = int(data.get('age', 6))
        gender = (data.get('gender') or 'neutral').strip()
        condition = (data.get('condition') or '').strip()
        hero_characteristics = (data.get('heroCharacteristics') or '').strip()
        child_id = data.get('childId')

        # 0. Content safety: validate & moderate input
        valid, error = validate_input(child_name, age, condition, hero_characteristics)
        if not valid:
            logger.warning(f'Input validation failed: {error}')
            return jsonify({'message': error}), 400

        # Load personalization data if a child profile is linked
        preferences = []
        story_history = []
        if child_id:
            try:
                preferences = db.get_preferences(child_id)
                story_history = db.get_child_story_history(child_id)
            except Exception as e:
                logger.warning(f'Failed to load personalization: {e}')

        # 1. Generate story text with Gemini
        gemini_key = os.environ.get('GEMINI_API_KEY', '')
        if not gemini_key:
            return jsonify({'message': 'GEMINI_API_KEY not configured'}), 500

        import google.generativeai as genai

        genai.configure(api_key=gemini_key)  # type: ignore[attr-defined]

        prompt = build_story_prompt(
            child_name=child_name, age=age, gender=gender,
            condition=condition, hero_characteristics=hero_characteristics,
            preferences=preferences, story_history=story_history,
        )

        with AIGenerationTracker('gemini', 'gemini-2.5-flash'):
            model = genai.GenerativeModel('gemini-2.5-flash')  # type: ignore[attr-defined]
            result = model.generate_content(prompt)
            content = result.text.strip()
            usage_counter.record('gemini', success=True)

        # Strip markdown code fences if present
        if content.startswith('```json'):
            content = content[7:]
        elif content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()

        story_data = json.loads(content)

        # 1b. Content safety: moderate AI output
        all_moderation_flags = []
        for page in story_data.get('pages', []):
            cleaned_text, warnings = moderate_output(page['text'], age)
            page['text'] = sanitize_html(cleaned_text)
            all_moderation_flags.extend(warnings)

            cleaned_prompt, img_warnings = moderate_image_prompt(page.get('imagePrompt', ''))
            page['imagePrompt'] = cleaned_prompt
            all_moderation_flags.extend(img_warnings)

        if all_moderation_flags:
            logger.warning(f'Moderation flags for story: {all_moderation_flags}')

        db.log_api_call('gemini', 'gemini-2.5-flash', True,
                        int((time.time() - start_time) * 1000), user_id=user_id or 0)

        # 2. Generate images with Flux 2 Pro
        flux_key = os.environ.get('FLUX2PRO_API_KEY', '')
        flux_endpoint = os.environ.get('FLUX2PRO_ENDPOINT', '')
        pages_with_images = []

        for idx, page in enumerate(story_data['pages']):
            image_url = None
            if flux_key and flux_endpoint and _image_storage:
                try:
                    import base64
                    img_prompt = build_image_prompt(
                        page['imagePrompt'], child_name, age,
                        gender, idx + 1, len(story_data['pages'])
                    )

                    max_retries = 2
                    last_err = None
                    for attempt in range(1, max_retries + 1):
                        try:
                            with AIGenerationTracker('flux2pro', 'flux-2-pro', page_num=idx + 1):
                                gen_resp = requests.post(
                                    flux_endpoint,
                                    headers={
                                        'Authorization': f'Bearer {flux_key}',
                                        'Content-Type': 'application/json',
                                    },
                                    json={
                                        'prompt': img_prompt,
                                        'width': 1024,
                                        'height': 1024,
                                        'n': 1,
                                        'model': 'FLUX.2-pro',
                                    },
                                    timeout=180,
                                )
                                gen_resp.raise_for_status()
                                gen_data = gen_resp.json()

                                b64_str = (gen_data.get('data') or [{}])[0].get('b64_json')
                                if b64_str:
                                    img_bytes = base64.b64decode(b64_str)
                                    img_name = f'story_{int(time.time())}_{idx + 1}.png'
                                    image_url = _image_storage.save_image(img_bytes, img_name)
                                    logger.info(f'Image saved (page {idx + 1}): {img_name}')

                                usage_counter.record('flux2pro', success=bool(image_url))
                                db.log_api_call('flux2pro', 'flux-2-pro', bool(image_url),
                                                user_id=user_id or 0)
                                last_err = None
                                break

                        except Exception as retry_e:
                            last_err = retry_e
                            logger.warning(f'Flux attempt {attempt}/{max_retries} failed: {retry_e}')
                            if attempt < max_retries:
                                time.sleep(2)

                    if last_err:
                        raise last_err

                except Exception as e:
                    logger.error(f'Image generation error page {idx + 1}: {e}')
                    usage_counter.record('flux2pro', success=False)
                    db.log_api_call('flux2pro', 'flux-2-pro', False,
                                    error_message=str(e), user_id=user_id or 0)

            pages_with_images.append({
                'text': page['text'],
                'imageUrl': image_url,
                'pageNumber': idx + 1,
            })

        # 3. Save to DB
        generation_time_ms = int((time.time() - start_time) * 1000)
        story = db.create_story(
            child_name=child_name, age=age, gender=gender,
            condition=condition, hero_characteristics=hero_characteristics,
            story_title=story_data.get('title', f"{child_name}'s Brave Adventure"),
            pages=pages_with_images, user_id=user_id or 0,
            child_id=child_id, moderation_flags=all_moderation_flags,
            generation_time_ms=generation_time_ms,
        )

        if not story:
            return jsonify({'message': 'Failed to save story'}), 500
        logger.info(f'Story generated in {generation_time_ms}ms: {story.get("storyTitle")}')
        return jsonify(story), 201

    except json.JSONDecodeError as e:
        logger.error(f'JSON parse error: {e}')
        usage_counter.record('gemini', success=False)
        return jsonify({'message': 'Failed to parse story from AI response'}), 500
    except Exception as e:
        logger.error(f'Story generation error: {e}', exc_info=True)
        return jsonify({'message': str(e)}), 500


# ── Feedback & Personalization Routes ─────────────────────────────────

@stories_bp.route('/api/stories/<int:story_id>/feedback', methods=['POST'])
def submit_feedback(story_id):
    """Record user feedback (rating, favourite page, read time) for a story."""
    data = request.get_json()
    story = db.get_story(story_id)
    if not story:
        return jsonify({'message': 'Story not found'}), 404

    child_id = story.get('child_id')
    if child_id:
        db.record_story_feedback(
            story_id=story_id, child_id=child_id,
            rating=data.get('rating'),
            favorite_page=data.get('favoritePage'),
            read_time_sec=data.get('readTimeSec', 0),
        )
        if data.get('rating') and data['rating'] >= 4:
            theme = story.get('theme', '')
            if theme:
                db.add_preference(child_id, 'theme', theme, weight=data['rating'] / 5.0)

    return jsonify({'success': True})


@stories_bp.route('/api/children/<int:child_id>/preferences', methods=['GET'])
@login_required
def get_preferences(child_id):
    """Return learned personalisation preferences for a child."""
    return jsonify(db.get_preferences(child_id))

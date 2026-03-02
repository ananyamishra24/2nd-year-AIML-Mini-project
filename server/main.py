import os
import sys
import json
import time
import requests
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, Response, g
from flask_cors import CORS
from dotenv import load_dotenv

BUILD_TS = str(int(time.time()))  # unique on every server restart

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / '.env')

# Add server dir to path for local imports
sys.path.insert(0, os.path.dirname(__file__))

# Use the new database_v2 (supports PostgreSQL + SQLite fallback)
import database_v2 as db

# Import new modules
from content_safety import validate_input, moderate_output, moderate_image_prompt, sanitize_html
from monitoring import setup_logging, ai_logger, api_logger, usage_counter, AIGenerationTracker, log_request, log_response
from prompt_manager import build_story_prompt, build_image_prompt
from cloud_storage import create_storage, download_and_store
from auth import (
    hash_password, verify_password, create_token,
    decode_token, validate_registration, login_required, optional_auth
)

import logging
setup_logging()
logger = logging.getLogger('brave_story.app')

app = Flask(__name__, static_folder=None)
CORS(app)

# Request/response logging
@app.before_request
def before_req():
    log_request()

@app.after_request
def after_req(response):
    return log_response(response)

@app.after_request
def add_no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

def serve_html(filename):
    """Serve an HTML file with cache-busted asset URLs."""
    html = (CLIENT_DIR / filename).read_text(encoding='utf-8')
    html = html.replace('/css/styles.css"', f'/css/styles.css?v={BUILD_TS}"')
    html = html.replace('/js/home.js"',   f'/js/home.js?v={BUILD_TS}"')
    html = html.replace('/js/create.js"', f'/js/create.js?v={BUILD_TS}"')
    html = html.replace('/js/story.js"',  f'/js/story.js?v={BUILD_TS}"')
    html = html.replace('/js/auth.js"',   f'/js/auth.js?v={BUILD_TS}"')
    return Response(html, mimetype='text/html')

# Init DB on startup
db.init_db()

# Static dirs
CLIENT_DIR = Path(__file__).parent.parent / 'client'
IMAGES_DIR = CLIENT_DIR / 'generated_images'
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Initialize cloud storage
image_storage = create_storage(str(IMAGES_DIR))

# ── Authentication Routes ─────────────────────────────────────────────

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    valid, error = validate_registration(data)
    if not valid:
        return jsonify({'message': error}), 400

    existing = db.get_user_by_email(data['email'])
    if existing:
        return jsonify({'message': 'Email already registered'}), 409

    pw_hash, salt = hash_password(data['password'])
    user = db.create_user(data['email'], data['name'], pw_hash, salt)
    if not user:
        return jsonify({'message': 'Failed to create user'}), 500
    token = create_token(user['id'], data['email'])
    logger.info(f'New user registered: {data["email"]}')
    return jsonify({'user': user, 'token': token}), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
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


@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_profile():
    user = db.get_user_by_id(g.user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify(user)


# ── Children Profile Routes ──────────────────────────────────────────

@app.route('/api/children', methods=['GET'])
@login_required
def list_children():
    return jsonify(db.get_children(g.user_id))


@app.route('/api/children', methods=['POST'])
@login_required
def add_child():
    data = request.get_json()
    child = db.create_child(
        g.user_id, data['name'], data['age'],
        data.get('gender', 'neutral'), data.get('conditions', [])
    )
    return jsonify(child), 201


@app.route('/api/children/<int:child_id>', methods=['PUT'])
@login_required
def update_child(child_id):
    data = request.get_json()
    child = db.update_child(child_id, **data)
    if not child:
        return jsonify({'message': 'Child not found'}), 404
    return jsonify(child)


@app.route('/api/children/<int:child_id>', methods=['DELETE'])
@login_required
def delete_child(child_id):
    if not db.delete_child(child_id):
        return jsonify({'message': 'Child not found'}), 404
    return jsonify({'success': True})

# ── Static file serving ──────────────────────────────────────────────

@app.route('/')
def serve_index():
    return serve_html('index.html')

@app.route('/create')
def serve_create():
    return serve_html('create.html')

@app.route('/login')
def serve_login():
    return serve_html('login.html')

@app.route('/story/<int:story_id>')
def serve_story(story_id):
    return serve_html('story.html')

@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(CLIENT_DIR / 'css', filename)

@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory(CLIENT_DIR / 'js', filename)

@app.route('/generated_images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)

# ── API Routes ────────────────────────────────────────────────────────

@app.route('/api/stories', methods=['GET'])
def list_stories():
    return jsonify(db.get_stories())

@app.route('/api/stories/favorites', methods=['GET'])
def favorite_stories():
    return jsonify(db.get_favorite_stories())

@app.route('/api/stories/<int:story_id>', methods=['GET'])
def get_story(story_id):
    story = db.get_story(story_id)
    if not story:
        return jsonify({'message': 'Story not found'}), 404
    return jsonify(story)

@app.route('/api/stories/<int:story_id>', methods=['DELETE'])
def delete_story(story_id):
    deleted = db.delete_story(story_id)
    if not deleted:
        return jsonify({'message': 'Story not found'}), 404
    return jsonify({'success': True, 'message': 'Story deleted successfully'})

@app.route('/api/stories/<int:story_id>/favorite', methods=['POST'])
def toggle_favorite(story_id):
    story = db.toggle_favorite(story_id)
    if not story:
        return jsonify({'message': 'Story not found'}), 404
    return jsonify(story)

@app.route('/api/stories/generate', methods=['POST'])
@optional_auth
def generate_story():
    start_time = time.time()
    user_id = getattr(g, 'user_id', None)

    try:
        data = request.get_json()
        child_name = data.get('childName', '').strip()
        age = int(data.get('age', 6))
        gender = data.get('gender', 'neutral').strip()
        condition = data.get('condition', '').strip()
        hero_characteristics = data.get('heroCharacteristics', '').strip()
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

        # 1. Generate story text with Gemini (using prompt manager)
        gemini_key = os.environ.get('GEMINI_API_KEY', '')
        if not gemini_key:
            return jsonify({'message': 'GEMINI_API_KEY not configured'}), 500

        import google.generativeai as genai
        genai.configure(api_key=gemini_key)

        prompt = build_story_prompt(
            child_name=child_name, age=age, gender=gender,
            condition=condition, hero_characteristics=hero_characteristics,
            preferences=preferences, story_history=story_history,
        )

        with AIGenerationTracker('gemini', 'gemini-2.5-flash'):
            model = genai.GenerativeModel('gemini-2.5-flash')
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

            # Moderate image prompts
            cleaned_prompt, img_warnings = moderate_image_prompt(page.get('imagePrompt', ''))
            page['imagePrompt'] = cleaned_prompt
            all_moderation_flags.extend(img_warnings)

        if all_moderation_flags:
            logger.warning(f'Moderation flags for story: {all_moderation_flags}')

        db.log_api_call('gemini', 'gemini-2.5-flash', True,
                       int((time.time() - start_time) * 1000), user_id=user_id or 0)

        # 2. Generate images with Flux 2 Pro (Black Forest Labs via Azure AI Foundry)
        flux_key = os.environ.get('FLUX2PRO_API_KEY', '')
        flux_endpoint = os.environ.get('FLUX2PRO_ENDPOINT', '')
        pages_with_images = []

        for idx, page in enumerate(story_data['pages']):
            image_url = None
            if flux_key and flux_endpoint:
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
                            with AIGenerationTracker('flux2pro', 'flux-2-pro', page_num=idx+1):
                                # Submit generation — returns base64 image synchronously
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
                                logger.info(f'Flux 2 Pro response (page {idx+1}, attempt {attempt}): keys={list(gen_data.keys())}')

                                # Response: data[0].b64_json (base64-encoded PNG)
                                b64_str = (gen_data.get('data') or [{}])[0].get('b64_json')
                                if b64_str:
                                    img_bytes = base64.b64decode(b64_str)
                                    img_name = f'story_{int(time.time())}_{idx + 1}.png'
                                    image_url = image_storage.save_image(img_bytes, img_name)
                                    logger.info(f'Flux 2 Pro image saved (page {idx+1}): {img_name}')
                                else:
                                    logger.warning(f'Flux 2 Pro: no b64_json in response (page {idx+1}): {gen_data}')

                                usage_counter.record('flux2pro', success=bool(image_url))
                                db.log_api_call('flux2pro', 'flux-2-pro', bool(image_url),
                                               user_id=user_id or 0)
                                last_err = None
                                break  # success — exit retry loop

                        except Exception as retry_e:
                            last_err = retry_e
                            logger.warning(f'Flux 2 Pro attempt {attempt}/{max_retries} failed for page {idx+1}: {retry_e}')
                            if attempt < max_retries:
                                logger.info(f'Retrying page {idx+1} image generation...')
                                time.sleep(2)

                    if last_err:
                        raise last_err

                except Exception as e:
                    logger.error(f'Image generation error page {idx+1}: {e}')
                    usage_counter.record('flux2pro', success=False)
                    db.log_api_call('flux2pro', 'flux-2-pro', False,
                                   error_message=str(e), user_id=user_id or 0)

            pages_with_images.append({
                'text': page['text'],
                'imageUrl': image_url,
                'pageNumber': idx + 1,
            })

        # 3. Save to DB (with user, personalization, and moderation data)
        generation_time_ms = int((time.time() - start_time) * 1000)
        story = db.create_story(
            child_name=child_name,
            age=age,
            gender=gender,
            condition=condition,
            hero_characteristics=hero_characteristics,
            story_title=story_data.get('title', f"{child_name}'s Brave Adventure"),
            pages=pages_with_images,
            user_id=user_id or 0,
            child_id=child_id,
            moderation_flags=all_moderation_flags,
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

@app.route('/api/stories/<int:story_id>/feedback', methods=['POST'])
def submit_feedback(story_id):
    data = request.get_json()
    story = db.get_story(story_id)
    if not story:
        return jsonify({'message': 'Story not found'}), 404

    child_id = story.get('child_id')
    if child_id:
        db.record_story_feedback(
            story_id=story_id,
            child_id=child_id,
            rating=data.get('rating'),
            favorite_page=data.get('favoritePage'),
            read_time_sec=data.get('readTimeSec', 0),
        )

        # Learn preferences from positive feedback
        if data.get('rating') and data['rating'] >= 4:
            theme = story.get('theme', '')
            if theme:
                db.add_preference(child_id, 'theme', theme, weight=data['rating'] / 5.0)

    return jsonify({'success': True})


@app.route('/api/children/<int:child_id>/preferences', methods=['GET'])
@login_required
def get_preferences(child_id):
    return jsonify(db.get_preferences(child_id))


# ── Admin / Monitoring Routes ─────────────────────────────────────────

@app.route('/api/admin/stats', methods=['GET'])
@login_required
def get_stats():
    return jsonify({
        'api_usage': db.get_api_usage_stats(),
        'today': usage_counter.get_today_stats(),
    })


# ── Azure Blob Storage Routes ─────────────────────────────────────────

@app.route('/api/storage/info', methods=['GET'])
@login_required
def storage_info():
    """Return current storage backend and config."""
    from cloud_storage import STORAGE_BACKEND, AZURE_CONTAINER, AWS_BUCKET, AWS_REGION
    return jsonify({
        'backend': STORAGE_BACKEND,
        'details': {
            's3_bucket': AWS_BUCKET or None,
            's3_region': AWS_REGION or None,
            'azure_container': AZURE_CONTAINER or None,
        }
    })


@app.route('/api/storage/blobs', methods=['GET'])
@login_required
def list_blobs():
    """List all blobs/images in Azure Blob container."""
    from cloud_storage import STORAGE_BACKEND, AZURE_CONN_STR, AZURE_CONTAINER
    if STORAGE_BACKEND != 'azure':
        return jsonify({'message': f'Storage backend is {STORAGE_BACKEND}, not azure'}), 400
    try:
        from azure.storage.blob import BlobServiceClient
        client = BlobServiceClient.from_connection_string(AZURE_CONN_STR)
        container = client.get_container_client(AZURE_CONTAINER)
        blobs = [
            {
                'name': b.name,
                'size': b.size,
                'created': b.creation_time.isoformat() if b.creation_time else None,
                'url': f'{client.url}{AZURE_CONTAINER}/{b.name}',
            }
            for b in container.list_blobs()
        ]
        return jsonify({'blobs': blobs, 'count': len(blobs)})
    except Exception as e:
        logger.error(f'Azure list blobs error: {e}')
        return jsonify({'message': str(e)}), 500


@app.route('/api/storage/blobs/<path:filename>', methods=['GET'])
@login_required
def get_blob_url(filename):
    """Get the public URL for a blob by filename."""
    from cloud_storage import STORAGE_BACKEND
    if STORAGE_BACKEND != 'azure':
        return jsonify({'message': f'Storage backend is {STORAGE_BACKEND}, not azure'}), 400
    try:
        url = image_storage.get_url(filename)
        return jsonify({'filename': filename, 'url': url})
    except Exception as e:
        logger.error(f'Azure get blob URL error: {e}')
        return jsonify({'message': str(e)}), 500


@app.route('/api/storage/blobs/<path:filename>', methods=['DELETE'])
@login_required
def delete_blob(filename):
    """Delete a blob from Azure Blob storage."""
    from cloud_storage import STORAGE_BACKEND
    if STORAGE_BACKEND != 'azure':
        return jsonify({'message': f'Storage backend is {STORAGE_BACKEND}, not azure'}), 400
    try:
        success = image_storage.delete_image(filename)
        if not success:
            return jsonify({'message': 'Blob not found or already deleted'}), 404
        logger.info(f'Blob deleted: {filename}')
        return jsonify({'success': True, 'deleted': filename})
    except Exception as e:
        logger.error(f'Azure delete blob error: {e}')
        return jsonify({'message': str(e)}), 500


@app.route('/api/storage/blobs/upload', methods=['POST'])
@login_required
def upload_blob():
    """Upload an image file directly to Azure Blob storage."""
    from cloud_storage import STORAGE_BACKEND
    if STORAGE_BACKEND != 'azure':
        return jsonify({'message': f'Storage backend is {STORAGE_BACKEND}, not azure'}), 400
    if 'file' not in request.files:
        return jsonify({'message': 'No file provided'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'message': 'Empty filename'}), 400
    try:
        filename = f'upload_{int(time.time())}_{file.filename}'
        url = image_storage.save_image(file.read(), filename)
        logger.info(f'Blob uploaded: {filename}')
        return jsonify({'success': True, 'filename': filename, 'url': url}), 201
    except Exception as e:
        logger.error(f'Azure upload error: {e}')
        return jsonify({'message': str(e)}), 500


if __name__ == '__main__':
    logger.info('🚀 Brave Story Maker server starting...')
    logger.info(f'📂 Serving client from: {CLIENT_DIR}')
    logger.info(f'💾 Storage backend: {image_storage.__class__.__name__}')
    app.run(host='0.0.0.0', port=5002, debug=True)

"""
FastAPI Async Backend for Brave Story Maker
────────────────────────────────────────────
Async handling of concurrent AI generation requests.
Uses all new modules: auth, content_safety, monitoring, prompt_manager, cloud_storage.
"""

import os
import sys
import json
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / '.env')

# Add server dir to path
sys.path.insert(0, os.path.dirname(__file__))

# Import our modules
import database_v2 as db
from auth import (
    hash_password, verify_password, create_token,
    decode_token, validate_registration
)
from content_safety import validate_input, moderate_output, moderate_image_prompt, sanitize_html
from monitoring import (
    setup_logging, ai_logger, api_logger, usage_counter,
    AIGenerationTracker
)
from prompt_manager import build_story_prompt, build_image_prompt
from cloud_storage import create_storage, download_and_store

# ── Setup logging ────────────────────────────────────────────────────
setup_logging()
logger = logging.getLogger('brave_story.app')

# ── Init ─────────────────────────────────────────────────────────────
app = FastAPI(title='Brave Story Maker', version='2.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Static dirs
CLIENT_DIR = Path(__file__).parent.parent / 'client'
IMAGES_DIR = CLIENT_DIR / 'generated_images'
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

BUILD_TS = str(int(time.time()))

# Init DB and storage
db.init_db()
storage = create_storage(str(IMAGES_DIR))


# ── Pydantic models ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ChildProfile(BaseModel):
    name: str
    age: int = Field(ge=2, le=18)
    gender: str = 'neutral'
    conditions: list = []

class StoryRequest(BaseModel):
    childName: str
    age: int = Field(ge=2, le=18)
    gender: str = 'neutral'
    condition: str
    heroCharacteristics: str = ''
    childId: Optional[int] = None

class FeedbackRequest(BaseModel):
    rating: Optional[int] = None
    favoritePage: Optional[int] = None
    readTimeSec: int = 0


# ── Auth helpers ─────────────────────────────────────────────────────

async def get_current_user(request: Request) -> Optional[dict]:
    """Extract user from Authorization header (optional)."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header[7:]
    payload = decode_token(token)
    if not payload:
        return None
    return payload


async def require_auth(request: Request) -> dict:
    """Require authentication."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail='Authentication required')
    return user


# ── HTML serving ─────────────────────────────────────────────────────

def serve_html(filename: str) -> HTMLResponse:
    html = (CLIENT_DIR / filename).read_text(encoding='utf-8')
    html = html.replace('/css/styles.css"', f'/css/styles.css?v={BUILD_TS}"')
    html = html.replace('/js/home.js"', f'/js/home.js?v={BUILD_TS}"')
    html = html.replace('/js/create.js"', f'/js/create.js?v={BUILD_TS}"')
    html = html.replace('/js/story.js"', f'/js/story.js?v={BUILD_TS}"')
    return HTMLResponse(html)


# ── Static & page routes ─────────────────────────────────────────────

@app.get('/')
async def index():
    return serve_html('index.html')

@app.get('/create')
async def create_page():
    return serve_html('create.html')

@app.get('/story/{story_id}')
async def story_page(story_id: int):
    return serve_html('story.html')

# Mount static directories
app.mount('/css', StaticFiles(directory=str(CLIENT_DIR / 'css')), name='css')
app.mount('/js', StaticFiles(directory=str(CLIENT_DIR / 'js')), name='js')
app.mount('/generated_images', StaticFiles(directory=str(IMAGES_DIR)), name='images')


# ── Auth routes ──────────────────────────────────────────────────────

@app.post('/api/auth/register')
async def register(data: RegisterRequest):
    valid, error = validate_registration(data.dict())
    if not valid:
        raise HTTPException(status_code=400, detail=error)

    existing = db.get_user_by_email(data.email)
    if existing:
        raise HTTPException(status_code=409, detail='Email already registered')

    pw_hash, salt = hash_password(data.password)
    user = db.create_user(data.email, data.name, pw_hash, salt)
    if not user:
        raise HTTPException(status_code=500, detail='Failed to create user')
    token = create_token(user['id'], data.email)
    logger.info(f'New user registered: {data.email}')
    return {'user': user, 'token': token}


@app.post('/api/auth/login')
async def login(data: LoginRequest):
    user_row = db.get_user_by_email(data.email)
    if not user_row:
        raise HTTPException(status_code=401, detail='Invalid email or password')

    if not verify_password(data.password, user_row['password_hash'], user_row['salt']):
        raise HTTPException(status_code=401, detail='Invalid email or password')

    db.update_last_login(user_row['id'])
    token = create_token(user_row['id'], data.email)
    user = db.get_user_by_id(user_row['id'])
    logger.info(f'User logged in: {data.email}')
    return {'user': user, 'token': token}


@app.get('/api/auth/me')
async def get_profile(user=Depends(require_auth)):
    profile = db.get_user_by_id(user['user_id'])
    if not profile:
        raise HTTPException(status_code=404, detail='User not found')
    return profile


# ── Children profiles ────────────────────────────────────────────────

@app.get('/api/children')
async def list_children(user=Depends(require_auth)):
    return db.get_children(user['user_id'])


@app.post('/api/children')
async def add_child(data: ChildProfile, user=Depends(require_auth)):
    child = db.create_child(user['user_id'], data.name, data.age, data.gender, data.conditions)
    return child


@app.put('/api/children/{child_id}')
async def update_child(child_id: int, data: ChildProfile, user=Depends(require_auth)):
    child = db.update_child(child_id, name=data.name, age=data.age,
                            gender=data.gender, conditions=data.conditions)
    if not child:
        raise HTTPException(status_code=404, detail='Child not found')
    return child


@app.delete('/api/children/{child_id}')
async def remove_child(child_id: int, user=Depends(require_auth)):
    if not db.delete_child(child_id):
        raise HTTPException(status_code=404, detail='Child not found')
    return {'success': True}


# ── Story routes ─────────────────────────────────────────────────────

@app.get('/api/stories')
async def list_stories(request: Request):
    user = await get_current_user(request)
    user_id = user['user_id'] if user else None
    return db.get_stories(user_id)


@app.get('/api/stories/favorites')
async def favorite_stories(request: Request):
    user = await get_current_user(request)
    user_id = user['user_id'] if user else None
    return db.get_favorite_stories(user_id)


@app.get('/api/stories/{story_id}')
async def get_story(story_id: int):
    story = db.get_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail='Story not found')
    return story


@app.delete('/api/stories/{story_id}')
async def delete_story(story_id: int):
    if not db.delete_story(story_id):
        raise HTTPException(status_code=404, detail='Story not found')
    return {'success': True, 'message': 'Story deleted successfully'}


@app.post('/api/stories/{story_id}/favorite')
async def toggle_favorite(story_id: int):
    story = db.toggle_favorite(story_id)
    if not story:
        raise HTTPException(status_code=404, detail='Story not found')
    return story


# ── Story generation (async) ─────────────────────────────────────────

@app.post('/api/stories/generate')
async def generate_story(data: StoryRequest, request: Request):
    start_time = time.time()
    user = await get_current_user(request)
    user_id = user['user_id'] if user else None

    # 1. Validate & moderate input
    valid, error = validate_input(
        data.childName, data.age, data.condition, data.heroCharacteristics
    )
    if not valid:
        raise HTTPException(status_code=400, detail=error)

    # 2. Get personalization data if child profile exists
    preferences = []
    story_history = []
    if data.childId:
        try:
            preferences = db.get_preferences(data.childId)
            story_history = db.get_child_story_history(data.childId)
        except Exception as e:
            logger.warning(f'Failed to load personalization data: {e}')

    # 3. Generate story text with Gemini
    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    if not gemini_key:
        raise HTTPException(status_code=500, detail='GEMINI_API_KEY not configured')

    prompt = build_story_prompt(
        child_name=data.childName,
        age=data.age,
        gender=data.gender,
        condition=data.condition,
        hero_characteristics=data.heroCharacteristics,
        preferences=preferences,
        story_history=story_history,
    )

    story_data = None
    with AIGenerationTracker('gemini', 'gemini-2.5-flash'):
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-2.5-flash')

            # Run in thread to not block event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: model.generate_content(prompt)
            )
            content = result.text.strip()

            # Strip markdown fences
            if content.startswith('```json'):
                content = content[7:]
            elif content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()

            story_data = json.loads(content)
            usage_counter.record('gemini', success=True)
            db.log_api_call('gemini', 'gemini-2.5-flash', True,
                           int((time.time() - start_time) * 1000),
                           user_id=user_id)
        except Exception as e:
            usage_counter.record('gemini', success=False)
            db.log_api_call('gemini', 'gemini-2.5-flash', False,
                           int((time.time() - start_time) * 1000),
                           error_message=str(e), user_id=user_id)
            logger.error(f'Gemini generation failed: {e}')
            raise HTTPException(status_code=500, detail=f'Story generation failed: {e}')

    # 4. Moderate story output
    all_moderation_flags = []
    for page in story_data.get('pages', []):
        cleaned_text, warnings = moderate_output(page['text'], data.age)
        page['text'] = sanitize_html(cleaned_text)
        all_moderation_flags.extend(warnings)

        # Moderate image prompts
        cleaned_prompt, img_warnings = moderate_image_prompt(page.get('imagePrompt', ''))
        page['imagePrompt'] = cleaned_prompt
        all_moderation_flags.extend(img_warnings)

    if all_moderation_flags:
        logger.warning(f'Moderation flags: {all_moderation_flags}')

    # 5. Generate images with Leonardo AI (async, concurrent)
    leonardo_key = os.environ.get('LEONARDO_API_KEY', '')
    pages_with_images = []

    async def generate_image_for_page(idx: int, page: dict) -> dict:
        image_url = None
        if leonardo_key:
            try:
                img_prompt = build_image_prompt(
                    page['imagePrompt'], data.childName, data.age,
                    data.gender, idx + 1, len(story_data['pages'])
                )

                async with httpx.AsyncClient(timeout=30) as client:
                    with AIGenerationTracker('leonardo', 'leonardo-ai', page_num=idx+1):
                        # Start generation
                        gen_resp = await client.post(
                            'https://cloud.leonardo.ai/api/rest/v1/generations',
                            headers={
                                'Authorization': f'Bearer {leonardo_key}',
                                'Content-Type': 'application/json',
                            },
                            json={
                                'prompt': img_prompt,
                                'num_images': 1,
                                'width': 1024,
                                'height': 1024,
                                'alchemy': True,
                                'photoReal': False,
                                'presetStyle': 'ILLUSTRATION',
                            },
                        )
                        gen_resp.raise_for_status()
                        generation_id = gen_resp.json()['sdGenerationJob']['generationId']
                        logger.info(f'Leonardo generation started: {generation_id} (page {idx+1})')

                        # Poll for completion
                        img_download_url = None
                        for _ in range(60):
                            await asyncio.sleep(2)
                            poll_resp = await client.get(
                                f'https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}',
                                headers={'Authorization': f'Bearer {leonardo_key}'},
                            )
                            poll_resp.raise_for_status()
                            gen_data = poll_resp.json().get('generations_by_pk', {})
                            status = gen_data.get('status')
                            if status == 'COMPLETE':
                                images = gen_data.get('generated_images', [])
                                if images:
                                    img_download_url = images[0].get('url')
                                break
                            elif status == 'FAILED':
                                logger.error(f'Leonardo generation FAILED for page {idx+1}')
                                break

                        if img_download_url:
                            # Download image
                            img_data = await client.get(img_download_url)
                            filename = f'story_{int(time.time())}_{idx + 1}.png'
                            image_url = storage.save_image(img_data.content, filename)

                        usage_counter.record('leonardo', success=bool(image_url))
                        db.log_api_call('leonardo', 'leonardo-ai', bool(image_url),
                                       user_id=user_id)

            except Exception as e:
                logger.error(f'Image generation error page {idx+1}: {e}')
                usage_counter.record('leonardo', success=False)
                db.log_api_call('leonardo', 'leonardo-ai', False,
                               error_message=str(e), user_id=user_id)

        return {
            'text': page['text'],
            'imageUrl': image_url,
            'pageNumber': idx + 1,
        }

    # Run all image generations concurrently
    tasks = [
        generate_image_for_page(idx, page)
        for idx, page in enumerate(story_data.get('pages', []))
    ]
    pages_with_images = await asyncio.gather(*tasks)

    # 6. Save to DB
    generation_time_ms = int((time.time() - start_time) * 1000)
    story = db.create_story(
        child_name=data.childName,
        age=data.age,
        gender=data.gender,
        condition=data.condition,
        hero_characteristics=data.heroCharacteristics,
        story_title=story_data.get('title', f"{data.childName}'s Brave Adventure"),
        pages=list(pages_with_images),
        user_id=user_id,
        child_id=data.childId,
        moderation_flags=all_moderation_flags,
        generation_time_ms=generation_time_ms,
    )

    if not story:
        raise HTTPException(status_code=500, detail='Failed to save story to database')

    logger.info(f'Story generated in {generation_time_ms}ms: {story.get("storyTitle")}')
    return JSONResponse(content=story, status_code=201)


# ── Feedback & personalization ───────────────────────────────────────

@app.post('/api/stories/{story_id}/feedback')
async def submit_feedback(story_id: int, data: FeedbackRequest, request: Request):
    user = await get_current_user(request)
    story = db.get_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail='Story not found')

    child_id = story.get('child_id')
    db.record_story_feedback(
        story_id=story_id,
        child_id=child_id,
        rating=data.rating,
        favorite_page=data.favoritePage,
        read_time_sec=data.readTimeSec,
    )

    # Update preferences based on feedback
    if child_id and data.rating and data.rating >= 4:
        theme = story.get('theme', '')
        if theme:
            db.add_preference(child_id, 'theme', theme, weight=data.rating / 5.0)

    return {'success': True}


@app.get('/api/children/{child_id}/preferences')
async def get_preferences(child_id: int, user=Depends(require_auth)):
    return db.get_preferences(child_id)


# ── Admin/monitoring routes ──────────────────────────────────────────

@app.get('/api/admin/stats')
async def get_stats(user=Depends(require_auth)):
    return {
        'api_usage': db.get_api_usage_stats(),
        'today': usage_counter.get_today_stats(),
    }


# ── Startup ──────────────────────────────────────────────────────────

@app.on_event('startup')
async def startup():
    logger.info('🚀 Brave Story Maker v2.0 starting (FastAPI async)...')
    logger.info(f'📂 Serving client from: {CLIENT_DIR}')
    logger.info(f'💾 Storage backend: {storage.__class__.__name__}')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        'app_fastapi:app',
        host='0.0.0.0',
        port=5002,
        reload=True,
        log_level='info',
    )

import os
import sys
import json
import time
import requests
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv

BUILD_TS = str(int(time.time()))  # unique on every server restart

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / '.env')

# Add server dir to path for local imports
sys.path.insert(0, os.path.dirname(__file__))
import database as db

app = Flask(__name__, static_folder=None)
CORS(app)

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
    return Response(html, mimetype='text/html')

# Init DB on startup
db.init_db()

# Static dirs
CLIENT_DIR = Path(__file__).parent.parent / 'client'
IMAGES_DIR = CLIENT_DIR / 'generated_images'
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# ── Static file serving ──────────────────────────────────────────────

@app.route('/')
def serve_index():
    return serve_html('index.html')

@app.route('/create')
def serve_create():
    return serve_html('create.html')

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
def generate_story():
    try:
        data = request.get_json()
        child_name = data.get('childName', '').strip()
        age = int(data.get('age', 6))
        gender = data.get('gender', 'neutral').strip()
        condition = data.get('condition', '').strip()
        hero_characteristics = data.get('heroCharacteristics', '').strip()

        if not child_name or not condition:
            return jsonify({'message': 'childName and condition are required'}), 400

        # 1. Generate story text with Gemini
        gemini_key = os.environ.get('GEMINI_API_KEY', '')
        if not gemini_key:
            return jsonify({'message': 'GEMINI_API_KEY not configured'}), 500

        import google.generativeai as genai
        genai.configure(api_key=gemini_key)

        traits_block = ''
        if hero_characteristics:
            traits_block = f"""
IMPORTANT - Hero Characteristics:
The hero {child_name} must consistently display these personality traits: {hero_characteristics}.
Make sure these characteristics:
- Shape the hero's decisions and actions in the story
- Are demonstrated through specific moments and dialogue
- Connect to how they overcome their medical challenge
- Provide moral lessons and inspirational messaging
"""

        prompt = f"""
Write a personalized children's story for a {age}-year-old {gender} named {child_name} who has {condition}.

The story must adapt based on the child's age:
- Ages 3–7: very simple words, short sentences, playful tone, 3 pages
- Ages 8–12: moderate vocabulary, engaging storytelling, 4 pages
- Ages 13+: natural language, motivational, 5 pages

The story should be empowering, turning the condition/treatment into a superpower.
{traits_block}
The tone should always remain warm, reassuring, brave, and supportive.

Return ONLY valid JSON with this exact structure:
{{
  "title": "Story Title",
  "pages": [
    {{
      "text": "Page 1 text here...",
      "imagePrompt": "Detailed illustration description, cartoon style, colorful."
    }}
  ]
}}
"""

        model = genai.GenerativeModel('gemini-2.5-flash')
        result = model.generate_content(prompt)
        content = result.text.strip()

        # Strip markdown code fences if present
        if content.startswith('```json'):
            content = content[7:]
        elif content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()

        story_data = json.loads(content)

        # 2. Generate images with DALL-E
        openai_key = os.environ.get('OPENAI_API_KEY', '')
        pages_with_images = []

        for idx, page in enumerate(story_data['pages']):
            image_url = None
            if openai_key:
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=openai_key)
                    img_prompt = (
                        f"{page['imagePrompt']}. "
                        "Children's book illustration style, colorful, warm, friendly, "
                        "whimsical digital art. Suitable for young readers."
                    )
                    resp = client.images.generate(
                        model='dall-e-3',
                        prompt=img_prompt,
                        n=1,
                        size='1024x1024',
                        quality='hd',
                        style='vivid',
                    )
                    url = resp.data[0].url if resp.data else None
                    if url:
                        img_resp = requests.get(url, timeout=30)
                        img_name = f'story_{int(time.time())}_{idx + 1}.png'
                        img_path = IMAGES_DIR / img_name
                        img_path.write_bytes(img_resp.content)
                        image_url = f'/generated_images/{img_name}'
                except Exception as e:
                    print(f'Image generation error page {idx+1}: {e}')

            pages_with_images.append({
                'text': page['text'],
                'imageUrl': image_url,
                'pageNumber': idx + 1,
            })

        # 3. Save to DB
        story = db.create_story(
            child_name=child_name,
            age=age,
            gender=gender,
            condition=condition,
            hero_characteristics=hero_characteristics,
            story_title=story_data.get('title', f"{child_name}'s Brave Adventure"),
            pages=pages_with_images,
        )
        return jsonify(story), 201

    except json.JSONDecodeError as e:
        print(f'JSON parse error: {e}')
        return jsonify({'message': 'Failed to parse story from AI response'}), 500
    except Exception as e:
        print(f'Story generation error: {e}')
        return jsonify({'message': str(e)}), 500


if __name__ == '__main__':
    print('🚀 Brave Story Maker server starting...')
    print(f'📂 Serving client from: {CLIENT_DIR}')
    app.run(host='0.0.0.0', port=5002, debug=True)

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Brave Story Maker is an AI-powered storybook generation platform for children facing medical challenges. It uses Anthropic Claude Sonnet 4.6 (via Azure AI Foundry's Anthropic-compatible endpoint) for story text, Azure OpenAI gpt-image-1.5 for illustrations (Studio Ghibli style), Azure OpenAI gpt-4o-mini-tts for expressive narration (steered via the `instructions` parameter for a child-audience bedside tone), and Azure OpenAI GPT-4o vision for the Moonface face-scanning feature.

## Commands

### Run the server
```bash
python server/main.py
```
Runs on `http://localhost:5002` with Flask debug mode enabled.

### Run tests
```bash
# All tests with coverage
python -m pytest tests/ -v --cov=server --cov-report=term-missing

# Single test file
python -m pytest tests/test_auth.py -v

# Single test
python -m pytest tests/test_auth.py::TestPasswordHashing::test_hash_returns_hash_and_salt -v

# By keyword
python -m pytest -k "password" -v
```

### Lint
```bash
# Errors only (CI-blocking)
flake8 server/ --count --select=E9,F63,F7,F82 --show-source --statistics

# All warnings
flake8 server/ --count --exit-zero --max-complexity=15 --max-line-length=120 --statistics
```

### Install dependencies
```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -r requirements.txt
```

## Architecture

### Backend (`server/`)
Flask app with Blueprint modules. Entry point is `server/main.py`.

| File | Role |
|------|------|
| `main.py` | App factory, rate limiting, cache-busting, static file serving (`/css/`, `/js/`, `/images/`, `/generated_images/`), CORS, security headers |
| `auth.py` | PBKDF2 password hashing, JWT signing, `@login_required` decorator |
| `database_v2.py` | All DB operations — SQLite by default, PostgreSQL via `DATABASE_URL` env var |
| `cloud_storage.py` | Storage abstraction — Local, S3, or Azure Blob (set by `STORAGE_BACKEND`) |
| `content_safety.py` | Input validation, XSS sanitization, blocked-terms filtering, output moderation |
| `prompt_manager.py` | Claude story prompts; Studio Ghibli image prompts (Section 7 structured format) with personalization and character builder |
| `tts_engine.py` | Azure OpenAI gpt-4o-mini-tts — `POST /openai/deployments/gpt-4o-mini-tts/audio/speech`. Returns MP3 bytes. Voices: coral (default), sage, ballad, nova, shimmer, alloy, echo, fable, onyx, ash. Injects a child-audience `instructions` steering prompt on every call. |
| `translator.py` | Azure AI Translator — `POST /translate?api-version=3.0`. Supports inline `<mstrans:dictionary>` markup so hero names (and other protected terms) pass through verbatim. Exposes `LANGUAGES`, `translate_batch()`, `is_rtl()`. |
| `monitoring.py` | Structured JSON logging, API call tracking |

### Routes (`server/routes/`)
| File | Key Endpoints |
|------|--------------|
| `auth.py` | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `PATCH /api/auth/profile`, `POST /api/auth/change-password`, `DELETE /api/auth/account`, `POST /api/auth/google`, `GET /api/auth/google/config` |
| `stories.py` | Story CRUD, `POST /api/stories/generate` (Claude Sonnet 4.6 text + Azure gpt-image-1.5), children profiles, feedback |
| `health.py` | `GET /api/health`, `GET /api/admin/stats`, storage management |
| `credits.py` | User and admin credit/usage dashboards |
| `speech.py` | `GET /api/tts/config`, `POST /api/tts` — gpt-4o-mini-tts proxy, returns `audio/mpeg` |
| `moonface.py` | `POST /api/moonface/analyze` — GPT-4o vision analyzes a captured JPEG, returns `skin_tone`, `hair_style`, `hair_color` |
| `translation.py` | `GET /api/translate/config`, `POST /api/translate` — Azure AI Translator proxy. Auto-protects the hero's name when `story_id` is passed. Returns `{translated, target_lang, direction}`. |

### Frontend (`client/`)
Vanilla HTML/CSS/JS — no build step. Flask serves files directly from `client/`. Each page has a corresponding JS file in `client/js/`. No bundler or framework.

| Page | Purpose |
|------|---------|
| `index.html` | Home / story library |
| `create.html` | Story creation form with character builder |
| `story.html` | Story viewer with AI narration, translation, favourites |
| `login.html` | Login / register with Google Sign-In |
| `profiles.html` | Netflix-style hero selector — fuzzy blob characters, Manage Heroes mode, Edit Hero modal with character builder and Moonface |
| `account.html` | Account settings — profile, password, delete account |
| `my-credits.html` | User credit/usage dashboard |
| `admin-credits.html` | Admin dashboard |
| `feedback.html` | Help & support / story rating |

Static UI images (e.g. `moonface-mirror.png`) live in `client/images/` and are served at `/images/<filename>`.

### Database Schema
Eight tables managed in `database_v2.py`: `users`, `children`, `stories`, `story_feedback`, `user_feedback`, `api_logs`, `preferences`, `credit_config`. Schema is auto-created on startup via `db.init_db()`.

- `stories.pages` is a JSON column storing `[{text, imageUrl, pageNumber}]`
- `stories.hero_character` stores the hero character JSON captured at generation time (added via migration)
- `children.heroCharacter` is a JSON column storing character builder selections: `skin_tone`, `hair_style`, `hair_color`, `outfit`, `accessory`, `medical_detail`, `birth_marks`
- `users.google_id` stores Google OAuth subject ID for accounts using Google Sign-In (added via `ALTER TABLE` migration on startup)
- Google-only accounts have empty `password_hash` and `salt` — `row_to_user()` sets `isGoogleUser: true`

### AI Pipeline (`server/routes/stories.py`)
Story generation flow:
1. Validate & sanitize inputs via `content_safety.py`
2. Build prompt via `prompt_manager.py` (includes optional hero character description)
3. Call Claude Sonnet 4.6 via Azure AI Foundry's Anthropic-compatible endpoint (`/anthropic/v1/messages`) → get story pages text (JSON with `title`, `theme`, `pages[]`)
4. For each page, call `build_image_prompt()` → structured Ghibli-style prompt → POST to Azure gpt-image-1.5
5. Upload image bytes (`b64_json` decoded) to configured storage backend
6. Save story to DB; return full story JSON

### Ghibli Image Style (`server/prompt_manager.py`)
All images are generated in Studio Ghibli cel-animation style (2004–2010 era). Three constants control this:
- `_GHIBLI_STYLE_PREAMBLE` — medium, colour palette, lighting, anatomy rules (Sections 1–2)
- `_GHIBLI_MEDICAL_SOFTENING` — auto-applied when scene contains medical keywords (Section 4)
- `_GHIBLI_EXCLUSIONS` — forbidden elements (no 3D, no photorealism, no text, etc.)

`build_image_prompt()` outputs the Section 7 structured format:
`[STYLE] / [CHARACTER] / [EXPRESSION] / [POSE] / [ACCESSORIES] / [BACKGROUND] / [COMPOSITION] / [MOOD] / [EXCLUSIONS]`

Gender maps to Ghibli character archetypes (boy = tousled dark hair + ochre shirt; girl = red-orange voluminous hair + red dress). The `illustration_style` dropdown from the create form is superseded — all stories render in Ghibli style.

### TTS Pipeline (`server/tts_engine.py` + `server/routes/speech.py`)
- `GET /api/tts/config` — returns `{ available, voices }`. Available when `AZURE_TTS_API_KEY` and `AZURE_TTS_ENDPOINT` are set
- `POST /api/tts` — proxies text to the gpt-4o-mini-tts deployment, returns `audio/mpeg`
- Backend uses the OpenAI-style JSON schema (`model`, `input`, `voice`, `instructions`, `response_format`, `speed`) — **not** SSML
- Every call includes a child-audience `instructions` prompt that steers the model toward a warm, unhurried, parent-reading-at-bedside delivery
- Voice IDs validated against server-side allowlist (`coral`, `sage`, `ballad`, `nova`, `shimmer`, `alloy`, `echo`, `fable`, `onyx`, `ash`); default is `coral`
- Speed clamped to 0.25–4.0; text truncated at 4096 chars
- Frontend caches audio blobs per `voice:lang:page` in memory — no re-fetch on page revisit
- Falls back to browser `speechSynthesis` if the Azure deployment is unavailable or fails

### Translation Pipeline (`server/translator.py` + `server/routes/translation.py`)
- `GET /api/translate/config` — returns `{ available, languages }` where each language has `{code, name, rtl}`
- `POST /api/translate` — JWT-required. Body: `{ texts: [...], target_lang: "hi", story_id?: 123 }`. Returns `{ translated: [...], target_lang, direction }`
- Uses Azure Translator v3.0. Multi-service resources must set `AZURE_TRANSLATOR_REGION`
- **Hero-name protection**: when `story_id` is provided, the backend looks up the story's `childName` and wraps it in `<mstrans:dictionary translation="...">` inline markup so Azure doesn't translate it. Frontend may also pass extra `protected_terms` explicitly
- Alias `zh` → `zh-Hans` applied server-side so the existing frontend dropdown keeps working
- RTL languages (`ar`, `ur`) return `direction: "rtl"`; frontend sets `dir="rtl"` on the text container
- Frontend caches translations in `transCache` per `lang:page` — no re-fetch on revisit

### Moonface (`server/routes/moonface.py`)
Camera-based hero character auto-fill feature on the profiles page.
- `POST /api/moonface/analyze` (JWT required) — accepts `{ image: "<base64 JPEG>" }`, calls GPT-4o vision, returns `{ skin_tone, hair_style, hair_color }`
- Valid `skin_tone` values: `light`, `medium-light`, `medium`, `medium-brown`, `brown`, `dark-brown`
- Valid `hair_style` values: `short straight`, `short curly`, `long straight`, `long curly`, `wavy`, `braids`, `pigtails`, `ponytail`, `high bun`, `afro`, `mohawk`, `buzz cut`
- Valid `hair_color` values: `black`, `brown`, `blonde`, `red`, `auburn`, `white`
- Unknown values are coerced to safe defaults before returning

### Hero Character Builder (`client/profiles.html` + `client/js/profiles.js`)
Edit Hero modal on the profiles page lets users customise their hero's appearance:
- **Skin Tone** — 6 color swatches
- **Hair Type** — 12 presets + ✏️ Custom free-text input
- **Hair Color** — 6 color swatches
- **Outfit** — 4 presets + ✏️ Custom free-text input
- **Accessory** — 4 presets (cape, shield, wand, backpack)
- **Medical Detail** — 5 presets + ✏️ Custom free-text input
- **Birth Marks** — always-visible free-text input

All fields saved into `children.heroCharacter` JSON. Moonface button opens the camera, captures a frame, and auto-fills Skin Tone, Hair Type, and Hair Color via GPT-4o vision.

### Google Sign-In Flow
- Frontend loads `https://accounts.google.com/gsi/client`, calls `GET /api/auth/google/config` to get the client ID
- On credential callback, POSTs Google ID token to `POST /api/auth/google`
- Backend verifies token with `google-auth` library, then: links to existing account by email, or creates a new account
- Returns a standard JWT — rest of the app is identical for Google and email/password users

## Key Environment Variables

| Variable | Purpose |
|----------|---------|
| `CLAUDE_API_KEY` | Azure AI Foundry API key for the Anthropic-compatible Claude deployment (required) |
| `CLAUDE_ENDPOINT` | Base URL of the Anthropic-compatible deployment, e.g. `https://<resource>.services.ai.azure.com/anthropic` — the SDK appends `/v1/messages` (required) |
| `CLAUDE_MODEL` | Model ID exposed via the Anthropic endpoint (default: `claude-sonnet-4-6`) |
| `AZURE_GPT_IMAGE_API_KEY` | Azure OpenAI gpt-image-1.5 — illustration generation (required) |
| `AZURE_GPT_IMAGE_ENDPOINT` | Full Azure endpoint URL including deployment + api-version (required) |
| `GPT4O_VISION_API_KEY` | Azure OpenAI GPT-4o — Moonface face scanning (required for Moonface) |
| `GPT4O_VISION_ENDPOINT` | Full Azure endpoint for GPT-4o chat completions (required for Moonface) |
| `AZURE_TTS_API_KEY` | Azure OpenAI key for the gpt-4o-mini-tts deployment (required for narration) |
| `AZURE_TTS_ENDPOINT` | Full deployment URL *including* api-version query, e.g. `https://<resource>.cognitiveservices.azure.com/openai/deployments/gpt-4o-mini-tts/audio/speech?api-version=2025-03-01-preview` |
| `AZURE_TRANSLATOR_KEY` | Azure AI Translator subscription key (required for /api/translate) |
| `AZURE_TRANSLATOR_ENDPOINT` | Default `https://api.cognitive.microsofttranslator.com/` |
| `AZURE_TRANSLATOR_REGION` | Azure region for multi-service Cognitive Services resources, e.g. `eastus2` |
| `JWT_SECRET_KEY` | JWT signing key (auto-generated if missing) |
| `TOKEN_EXPIRY_HOURS` | JWT expiry (default: 72) |
| `DATABASE_URL` | Empty = SQLite; `postgres://...` for PostgreSQL |
| `STORAGE_BACKEND` | `local`, `s3`, or `azure` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (optional — enables Google Sign-In) |

Copy `.env.example` to `.env` to get started.

## Testing Notes

- Tests use an in-memory SQLite DB (never touches the real DB)
- Rate limiting is disabled in test mode
- Storage is forced to `local` in tests
- Fixtures are in `tests/conftest.py`: `app`, `client`, `auth_header`
- `auth_header` provides a pre-registered user's JWT — use it for authenticated route tests
- Data isolation is tested in `tests/test_data_isolation.py` — every query must filter by `user_id`

## Security Patterns

- Every protected route uses `@login_required` — the decorator extracts `user_id` from the JWT and injects it into `g.user_id`
- User data isolation: always filter DB queries by `g.user_id`; use `verify_child_owner()` / `verify_story_owner()` helpers
- All user text input goes through `content_safety.sanitize_html()` before storage or use in prompts
- Do not use `SELECT *` or unparameterized queries — `database_v2.py` uses parameterized queries throughout
- CSRF is mitigated by using `Authorization: Bearer` header (not cookies) — tokens cannot be attached automatically by browsers
- Azure TTS and GPT-4o API keys are never exposed to the frontend — all requests are proxied through the backend
- TTS voice IDs are validated against a server-side allowlist before forwarding to Azure
- Google Sign-In tokens are verified server-side using `google.oauth2.id_token.verify_oauth2_token()`
- Camera access is permitted via `Permissions-Policy: camera=(self)`; all other sensitive permissions are blocked

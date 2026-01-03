# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ShipFlow app that automates viral video creation:
1. Research trending news via Perplexity AI
2. Write video scripts via OpenAI
3. Create AI avatar videos via HeyGen
4. Post to 9 social platforms via Blotato

Converted from an n8n workflow to a standalone Python/Next.js application.

## Commands

### Run with Docker (recommended)
```bash
docker-compose up --build
```
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Backend Development
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env   # then edit with your API keys
uvicorn app:app --reload
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

### Test Full Workflow
```bash
curl -X POST http://localhost:8000/workflow/run \
  -H "Content-Type: application/json" \
  -d '{"industry": "real estate", "platforms": ["tiktok", "instagram"]}'
```

### List HeyGen Avatars (troubleshooting)
```bash
curl http://localhost:8000/heygen/talking-photos
```

## Architecture

```
shipflow-app/
├── backend/                    # Python FastAPI
│   ├── app.py                 # Main API + workflow orchestration
│   ├── sdk/                   # Type-safe API clients
│   │   ├── heygen.py         # HeyGen video generation
│   │   ├── blotato.py        # Social media posting
│   │   ├── config_validator.py
│   │   └── errors.py
│   └── optimizer/             # Self-improving workflow system
│       ├── metrics.py        # Performance tracking
│       ├── experiments.py    # A/B testing
│       └── improvement_engine.py
├── frontend/                  # Next.js 14 + React + Tailwind
│   └── src/app/page.tsx      # Main dashboard UI
└── docker-compose.yml
```

### Key Backend Components

**app.py** - Main orchestration:
- `create_heygen_video()` - Creates avatar video (lines 226-312)
- `wait_for_video()` - Polls HeyGen until ready (lines 332-345)
- `run_full_workflow()` - Full 7-step pipeline (lines 439-548)

**sdk/heygen.py** - Type-safe HeyGen client:
- Distinguishes `TalkingPhotoConfig` (from photos) vs `VideoAvatarConfig` (from videos)
- Handles "completed but URL missing" edge case that raw API doesn't

**sdk/blotato.py** - Platform-specific post types with validation

## HeyGen Avatar Configuration

Critical: HeyGen has two avatar types requiring different API parameters:

| Avatar Type | Created From | Config Class | ID Source |
|-------------|--------------|--------------|-----------|
| `talking_photo` | Photo upload | `TalkingPhotoConfig` | `/v1/talking_photo.list` |
| `avatar` | Video upload or public preset | `VideoAvatarConfig` | `/v2/avatars` |

Environment variables in `backend/.env`:
```
HEYGEN_AVATAR_TYPE=talking_photo  # or "avatar"
HEYGEN_TALKING_PHOTO_ID=xxx       # if type=talking_photo
HEYGEN_AVATAR_ID=xxx              # if type=avatar (e.g., Anna_public_3_20240108)
```

## Workflow Steps

1. **Research** - Perplexity finds top 10 trending news
2. **Select** - Perplexity picks most viral story
3. **Write** - OpenAI generates script, caption, title
4. **Create Video** - HeyGen generates AI avatar video
5. **Wait** - Poll until video ready (up to 10 min)
6. **Upload** - Upload to Blotato
7. **Post** - Publish to selected platforms

## n8n Workflow Architecture

The workflow has 3 main sections:

### 1. Content Generation (AI Agent)
```
Schedule Trigger (10am daily)
    ↓
AI Agent → Perplexity researches top 10 news → Selects most viral story
    ↓
OpenAI writes: script, long caption, short caption, title
```

### 2. HeyGen Video Creation
```
Setup HeyGen (avatar ID, voice ID, background settings)
    ↓
┌─────────────────────────────────────────────┐
│ IF has_background_video = true:             │
│   → Create Avatar Video WITH Background     │
│ ELSE:                                       │
│   → Create Avatar Video WITHOUT Background  │
└─────────────────────────────────────────────┘
    ↓
Merge → Wait → Get Avatar Video
```

**Key settings:**
- `has_background_video`: Set to `true` only if avatar has background removed (higher tier plan)
- `background_video_url`: URL of background video/image
- Enable captions in CREATE HEYGEN VIDEO step
- Use `video_url_caption` from GET VIDEO step for captioned version

### 3. Multi-Platform Posting (Blotato)
```
Pass video URL directly to Blotato (no upload step needed)
    ↓
Post in parallel to:
├── Facebook    ├── TikTok     ├── Threads
├── Instagram   ├── YouTube    └── Bluesky
└── Tumblr
```

**Note:** Blotato handles media upload internally - just pass the video URL directly.

### Testing Tips
- Enable only 1 social platform during testing
- Use 5-second scripts (not 30s) to reduce HeyGen processing time
- Check HeyGen dashboard to verify video is processing
- Use Blotato API Dashboard (`my.blotato.com`) to debug errors

## Required Environment Variables

See `backend/.env.example` for full list. Essential:
- `PERPLEXITY_API_KEY`
- `OPENAI_API_KEY`
- `HEYGEN_API_KEY`, `HEYGEN_AVATAR_TYPE`, avatar ID, `HEYGEN_VOICE_ID`
- `BLOTATO_API_KEY` + account IDs for each platform

## Known Issues

- HeyGen videos can get stuck in "processing" - this is HeyGen's service, not code
- If video shows wrong avatar, verify ID via `/heygen/talking-photos` endpoint
- Blotato requires platform-specific account IDs (see MANUAL_STEPS.md)

## Debugging Protocol

**IMPORTANT: Before debugging ANY error in this project:**
1. Read `GOTCHAS.md` first - it contains 50+ documented issues and fixes
2. Search for keywords related to the error (e.g., "avatar", "video_id", "webhook")
3. Check the error against known patterns before investigating from scratch

Common error categories in GOTCHAS.md:
- HeyGen avatar types (#53) - avatar vs talking_photo confusion
- n8n expression syntax (#1-10) - $json vs $('Node').item references
- HeyGen polling patterns (#21) - async video generation
- Blotato platform posting (#30-40) - account ID requirements

## Universal Coding Rules & Best Practices

### 1. The "0.1%" Elite Standards
- **Strong Typing:** Always use strict types (e.g., TypeScript, Pydantic). Avoid `any` at all costs.
- **Zero Warnings:** The console, linter, and compiler must be completely empty. Treat warnings as errors.
- **Automated Safety:** Never commit code without running tests and linting first.
- **Clean Architecture:** Separate your logic (how it works) from your UI (how it looks).

### 2. When to Refactor (Clean Up)
- **The Rule of Three:** If you copy-paste code 3 times, turn it into a single function.
- **The "Squint" Test:** If you have to squint or scroll to understand a function, it is too long. Break it up.
- **Bug Magnets:** If you fix a bug in a file and it breaks something else, that file is too complex. Rewrite it.
- **Hard to Read:** If you can't explain the code to a 5-year-old, rewrite it to be simpler.

### 3. Efficiency & Resource Saving
- **Plan First:** Write a plan in English before writing code. Deleting code costs time and energy.
- **Don't Reinvent:** Check if a library or built-in function already exists before writing a new one.
- **Test Small:** Test individual functions before running the whole app to catch bugs cheaply.
- **Keep it Simple:** The simplest solution is usually the most efficient.

### 4. Beginner Safety Net
- **Clear Naming:** Use names like `userAddress` instead of `ua`.
- **One Job:** A function should do one thing only.
- **Comment Why, Not What:** Code shows what it does; comments explain why.
- **Fail Fast:** Validate inputs early and return clear error messages.

"""
Viral News to AI Avatar Videos - FastAPI Backend
Converted from n8n workflow using ShipFlow

This app:
1. Researches trending news via Perplexity AI
2. Writes video scripts via OpenAI
3. Creates AI avatar videos via HeyGen
4. Posts to 9 social platforms via Blotato
"""

print("=== VERSION 2024-12-25 YOUTUBE+TIKTOK FIX ===")
print(f"=== RUNNING FROM: {__file__} ===")

import os
import asyncio
import logging
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI

# Self-Improving Optimizer imports
from optimizer import (
    Database,
    MetricsCollector,
    ConfigStore,
    ExperimentManager,
    ImprovementEngine,
    RollbackGuard,
)
from optimizer.workflow_wrapper import OptimizedWorkflow

# SDK imports - Type-safe API clients with built-in validation
from sdk import (
    # HeyGen
    HeyGenClient,
    TalkingPhotoConfig,
    VideoAvatarConfig,
    VoiceConfig,
    # Blotato
    BlotaoClient,
    TikTokPost,
    FacebookPost,
    InstagramPost,
    YouTubePost,
    PinterestPost,
    TwitterPost,
    BlueskyPost,
    # Validation
    ConfigValidator,
)
from sdk.config_validator import validate_config_or_exit

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
    HEYGEN_VOICE_ID = os.getenv("HEYGEN_VOICE_ID")
    BLOTATO_API_KEY = os.getenv("BLOTATO_API_KEY")

    # HeyGen Avatar Configuration
    # IMPORTANT: HeyGen has different avatar types!
    # - "talking_photo" = created from a PHOTO (use HEYGEN_TALKING_PHOTO_ID)
    # - "avatar" = created from a VIDEO or public avatar (use HEYGEN_AVATAR_ID)
    HEYGEN_AVATAR_TYPE = os.getenv("HEYGEN_AVATAR_TYPE", "talking_photo")  # "talking_photo" or "avatar"
    HEYGEN_TALKING_PHOTO_ID = os.getenv("HEYGEN_TALKING_PHOTO_ID")
    HEYGEN_AVATAR_ID = os.getenv("HEYGEN_AVATAR_ID")

    # Optional: Background video URL for avatar
    HEYGEN_BACKGROUND_VIDEO_URL = os.getenv(
        "HEYGEN_BACKGROUND_VIDEO_URL",
        ""
    )
    HEYGEN_HAS_BACKGROUND = os.getenv("HEYGEN_HAS_BACKGROUND", "false").lower() == "true"

    # Industry to research (customizable)
    INDUSTRY = os.getenv("INDUSTRY", "real estate")

    # Blotato Account IDs
    BLOTATO_BLUESKY_ACCOUNT_ID = os.getenv("BLOTATO_BLUESKY_ACCOUNT_ID")
    BLOTATO_FACEBOOK_ACCOUNT_ID = os.getenv("BLOTATO_FACEBOOK_ACCOUNT_ID")
    BLOTATO_FACEBOOK_PAGE_ID = os.getenv("BLOTATO_FACEBOOK_PAGE_ID")
    BLOTATO_YOUTUBE_ACCOUNT_ID = os.getenv("BLOTATO_YOUTUBE_ACCOUNT_ID")
    BLOTATO_INSTAGRAM_ACCOUNT_ID = os.getenv("BLOTATO_INSTAGRAM_ACCOUNT_ID")
    BLOTATO_PINTEREST_ACCOUNT_ID = os.getenv("BLOTATO_PINTEREST_ACCOUNT_ID")
    BLOTATO_TIKTOK_ACCOUNT_ID = os.getenv("BLOTATO_TIKTOK_ACCOUNT_ID")
    BLOTATO_TWITTER_ACCOUNT_ID = os.getenv("BLOTATO_TWITTER_ACCOUNT_ID")


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class WorkflowInput(BaseModel):
    """Input for manual trigger of the workflow"""
    industry: str = Field(default="real estate", description="Industry to research news for")
    script_length_seconds: int = Field(default=30, description="Target video length in seconds")
    platforms: list[str] = Field(
        default=["tiktok", "instagram", "youtube"],
        description="Social platforms to post to"
    )

class WorkflowStatus(BaseModel):
    """Status response for workflow execution"""
    status: str
    step: str
    message: str
    data: Optional[dict] = None

class ScriptOutput(BaseModel):
    """Output from the AI Writer"""
    script: str
    caption: str
    title: str

class VideoStatus(BaseModel):
    """HeyGen video status"""
    video_id: str
    status: str
    video_url: Optional[str] = None


# =============================================================================
# API CLIENTS
# =============================================================================

async def call_perplexity(prompt: str) -> str:
    """Call Perplexity AI for research"""
    if not Config.PERPLEXITY_API_KEY:
        raise HTTPException(status_code=500, detail="PERPLEXITY_API_KEY not configured")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {Config.PERPLEXITY_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "sonar-pro",
                "messages": [{"role": "user", "content": prompt}],
                "search_recency_filter": "day"
            }
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def call_openai_writer(news_report: str) -> ScriptOutput:
    """Call OpenAI to write video script, caption, and title"""
    if not Config.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    client = OpenAI(api_key=Config.OPENAI_API_KEY)

    system_prompt = f"""# TASK
1. Analyze the following viral news story:
<news>
{news_report}
</news>

2. Write a conversational monologue script for an AI avatar video, following these guidelines:
   - The script should be approximately 30 seconds when spoken aloud.
   - Include lots of factual details and statistics from the article.
   - Use 6th grade reading level.
   - Balanced viewpoint.
   - First sentence should create an irresistible curiosity gap to hook viewers.
   - Replace the last sentence with this CTA: "Hit follow to stay up to date!"
   - ONLY output the exact video script. Do not output anything else. NEVER include intermediate thoughts, notes, or formatting.

3. Write an SEO-optimized caption that will accompany the video, max 5 hashtags.

4. Write 1 viral sentence, max 8 words, summarizing the content, use 6th grade language, balanced neutral perspective, no emojis, no punctuation except `?` or `!`.

# OUTPUT

You will output structured JSON in the following format:
{{
  "script": "Monologue script to be spoken by AI avatar",
  "caption": "Long SEO-optimized video caption",
  "title": "Short video title"
}}"""

    response = client.chat.completions.create(
        model="o1",  # Using OpenAI's o1 model as requested
        messages=[{"role": "user", "content": system_prompt}],
    )

    content = response.choices[0].message.content

    # Parse JSON from response
    import json
    try:
        # Try to extract JSON from the response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())
        return ScriptOutput(**data)
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse OpenAI response: {content}")
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")


async def create_heygen_video(script: str, title: str, with_background: bool = False) -> str:
    """Create AI avatar video via HeyGen API"""
    if not Config.HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HEYGEN_API_KEY not configured")

    # Build character config based on avatar type
    # IMPORTANT: HeyGen has different avatar types with different API parameters!
    # - "talking_photo" = created from a PHOTO (use talking_photo_id)
    # - "avatar" = created from a VIDEO or public avatar (use avatar_id)
    if Config.HEYGEN_AVATAR_TYPE == "talking_photo":
        if not Config.HEYGEN_TALKING_PHOTO_ID:
            raise HTTPException(status_code=500, detail="HEYGEN_TALKING_PHOTO_ID not configured")
        character = {
            "type": "talking_photo",
            "talking_photo_id": Config.HEYGEN_TALKING_PHOTO_ID
        }
        logger.info(f"Using Talking Photo avatar: {Config.HEYGEN_TALKING_PHOTO_ID}")
    else:
        if not Config.HEYGEN_AVATAR_ID:
            raise HTTPException(status_code=500, detail="HEYGEN_AVATAR_ID not configured")
        character = {
            "type": "avatar",
            "avatar_id": Config.HEYGEN_AVATAR_ID,
            "avatar_style": "normal",
            "scale": 1.0
        }
        logger.info(f"Using Video/Public avatar: {Config.HEYGEN_AVATAR_ID}")

    # Build video request
    video_input = {
        "character": character,
        "voice": {
            "type": "text",
            "input_text": script,
            "voice_id": Config.HEYGEN_VOICE_ID,
            "speed": 1.1,
            "pitch": 50,
            "emotion": "Excited"
        }
    }

    # Add background if configured (only works with video avatars, not talking photos)
    if with_background and Config.HEYGEN_BACKGROUND_VIDEO_URL and Config.HEYGEN_AVATAR_TYPE != "talking_photo":
        video_input["character"]["offset"] = {"x": 0.15, "y": 0.15}
        video_input["character"]["matting"] = True
        video_input["background"] = {
            "type": "video",
            "url": Config.HEYGEN_BACKGROUND_VIDEO_URL,
            "play_style": "loop",
            "fit": "cover"
        }

    payload = {
        "video_inputs": [video_input],
        "dimension": {"width": 720, "height": 1280},
        "aspect_ratio": "9:16",
        "caption": True,
        "subtitles": {
            "preset_name": "default",
            "font_size": 12,
            "bottom_align": True
        },
        "title": title
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.heygen.com/v2/video/generate",
            headers={
                "X-Api-Key": Config.HEYGEN_API_KEY,
                "Content-Type": "application/json"
            },
            json=payload
        )

        # Log the response for debugging
        logger.info(f"HeyGen response status: {response.status_code}")
        logger.info(f"HeyGen response body: {response.text}")

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"HeyGen API error: {response.text}"
            )

        data = response.json()
        return data["data"]["video_id"]


async def get_heygen_video_status(video_id: str) -> VideoStatus:
    """Check HeyGen video generation status"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://api.heygen.com/v1/video_status.get",
            headers={"X-Api-Key": Config.HEYGEN_API_KEY},
            params={"video_id": video_id}
        )
        response.raise_for_status()
        data = response.json()["data"]
        return VideoStatus(
            video_id=video_id,
            status=data["status"],
            video_url=data.get("video_url")
        )


async def wait_for_video(video_id: str, max_attempts: int = 30, delay: int = 20) -> str:
    """Poll HeyGen until video is ready"""
    for attempt in range(max_attempts):
        status = await get_heygen_video_status(video_id)
        logger.info(f"Video {video_id} status: {status.status} (attempt {attempt + 1}/{max_attempts})")

        if status.status == "completed":
            return status.video_url
        elif status.status == "failed":
            raise HTTPException(status_code=500, detail="HeyGen video generation failed")

        await asyncio.sleep(delay)

    raise HTTPException(status_code=504, detail="Video generation timed out")


async def upload_to_blotato(video_url: str) -> str:
    """Upload video to Blotato and get media URL"""
    if not Config.BLOTATO_API_KEY:
        raise HTTPException(status_code=500, detail="BLOTATO_API_KEY not configured")

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://backend.blotato.com/v2/media",
            headers={
                "blotato-api-key": Config.BLOTATO_API_KEY,
                "Content-Type": "application/json"
            },
            json={"url": video_url}
        )
        response.raise_for_status()
        data = response.json()
        return data["url"]


async def post_to_platform(
    platform: str,
    account_id: str,
    text: str,
    media_url: str,
    title: Optional[str] = None
) -> dict:
    """Post content to a social platform via Blotato"""
    # Blotato API expects just the numeric account ID (no prefix)
    # Remove acc_ prefix if present
    if account_id and account_id.startswith("acc_"):
        account_id = account_id[4:]

    # Build target object based on platform
    target = {"targetType": platform}

    # Platform-specific target options
    if platform == "facebook" and Config.BLOTATO_FACEBOOK_PAGE_ID:
        target["pageId"] = Config.BLOTATO_FACEBOOK_PAGE_ID

    if platform == "youtube":
        target["title"] = title or "Video"
        target["containsSyntheticMedia"] = True
        target["privacyStatus"] = "public"
        target["shouldNotifySubscribers"] = True

    if platform == "tiktok":
        target["isAiGenerated"] = True
        target["privacyLevel"] = "PUBLIC_TO_EVERYONE"
        target["disabledComments"] = False
        target["disabledDuet"] = False
        target["disabledStitch"] = False
        target["isBrandedContent"] = False
        target["isYourBrand"] = False

    # Blotato API v2 structure - post object wraps everything
    payload = {
        "post": {
            "accountId": account_id,
            "content": {
                "text": text,
                "mediaUrls": [media_url],
                "platform": platform
            },
            "target": target
        }
    }

    import json
    logger.info(f"Posting to {platform}: accountId={account_id}, target={target}")
    print(f"\n{'='*60}")
    print(f"DEBUG BLOTATO PAYLOAD FOR {platform.upper()}:")
    print(json.dumps(payload, indent=2))
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://backend.blotato.com/v2/posts",
            headers={
                "blotato-api-key": Config.BLOTATO_API_KEY,
                "Content-Type": "application/json"
            },
            json=payload
        )
        logger.info(f"Blotato response for {platform}: {response.status_code}")
        response.raise_for_status()
        return response.json()


# =============================================================================
# MAIN WORKFLOW
# =============================================================================

async def run_full_workflow(input_data: WorkflowInput) -> dict:
    """Execute the complete viral news to AI avatar workflow"""
    results = {
        "started_at": datetime.now().isoformat(),
        "industry": input_data.industry,
        "steps": {}
    }

    try:
        # Step 1: Research top 10 news
        logger.info(f"Step 1: Researching top 10 {input_data.industry} news...")
        top_10_prompt = f"Research the top 10 trending news items in my industry from the past 24 hours.\n\n- Industry: {input_data.industry}"
        top_10_news = await call_perplexity(top_10_prompt)
        results["steps"]["research_top_10"] = {"status": "completed", "preview": top_10_news[:200]}

        # Step 2: Deep research on best story
        logger.info("Step 2: Deep research on most viral story...")
        report_prompt = f"""# INSTRUCTIONS

Complete the following tasks, in order:

1. Out of the 10 news stories listed below, select the ONE top news story that is most likely to go viral on social media. It should have broad appeal and contain something unique, controversial, or vitally important information that millions of people should know.

<news>
{top_10_news}
</news>

2. Research more information about the top news story you selected.

3. Your final output should be a detailed report of the top story you've selected. It should be dense with factual data, statistics, sources, and key information based on your research. Include reasons why this story would perform well on social media. Include why a "normal person" in this industry should care about this news."""

        news_report = await call_perplexity(report_prompt)
        results["steps"]["research_report"] = {"status": "completed", "preview": news_report[:200]}

        # Step 3: Write script
        logger.info("Step 3: Writing video script...")
        script_output = call_openai_writer(news_report)
        results["steps"]["write_script"] = {
            "status": "completed",
            "script_preview": script_output.script[:100],
            "title": script_output.title
        }

        # Step 4: Create HeyGen video
        logger.info("Step 4: Creating AI avatar video...")
        video_id = await create_heygen_video(
            script=script_output.script,
            title=script_output.title,
            with_background=Config.HEYGEN_HAS_BACKGROUND
        )
        results["steps"]["create_video"] = {"status": "processing", "video_id": video_id}

        # Step 5: Wait for video
        logger.info(f"Step 5: Waiting for video {video_id}...")
        video_url = await wait_for_video(video_id)
        results["steps"]["create_video"]["status"] = "completed"
        results["steps"]["create_video"]["video_url"] = video_url

        # Step 6: Upload to Blotato
        logger.info("Step 6: Uploading to Blotato...")
        media_url = await upload_to_blotato(video_url)
        results["steps"]["upload_media"] = {"status": "completed", "media_url": media_url}

        # Step 7: Post to platforms
        logger.info("Step 7: Posting to social platforms...")
        platform_accounts = {
            "bluesky": Config.BLOTATO_BLUESKY_ACCOUNT_ID,
            "facebook": Config.BLOTATO_FACEBOOK_ACCOUNT_ID,  # Account ID, pageId added in post_to_platform()
            "youtube": Config.BLOTATO_YOUTUBE_ACCOUNT_ID,
            "instagram": Config.BLOTATO_INSTAGRAM_ACCOUNT_ID,
            "pinterest": Config.BLOTATO_PINTEREST_ACCOUNT_ID,
            "tiktok": Config.BLOTATO_TIKTOK_ACCOUNT_ID,
            "twitter": Config.BLOTATO_TWITTER_ACCOUNT_ID,
        }

        post_results = {}
        for platform in input_data.platforms:
            account_id = platform_accounts.get(platform)
            if not account_id:
                post_results[platform] = {"status": "skipped", "reason": "No account ID configured"}
                continue

            try:
                result = await post_to_platform(
                    platform=platform,
                    account_id=account_id,
                    text=script_output.caption,
                    media_url=media_url,
                    title=script_output.title if platform == "youtube" else None
                )
                post_results[platform] = {"status": "completed", "result": result}
                logger.info(f"Posted to {platform} successfully")
            except Exception as e:
                post_results[platform] = {"status": "failed", "error": str(e)}
                logger.error(f"Failed to post to {platform}: {e}")

        results["steps"]["post_to_platforms"] = {
            "status": "completed",
            "platforms": post_results
        }

        results["completed_at"] = datetime.now().isoformat()
        results["status"] = "completed"

    except Exception as e:
        logger.exception("Workflow failed")
        results["status"] = "failed"
        results["error"] = str(e)

    return results


# =============================================================================
# FASTAPI APP
# =============================================================================

# =============================================================================
# OPTIMIZER INITIALIZATION (Global instances)
# =============================================================================

optimizer_db: Optional[Database] = None
metrics_collector: Optional[MetricsCollector] = None
config_store: Optional[ConfigStore] = None
experiment_manager: Optional[ExperimentManager] = None
improvement_engine: Optional[ImprovementEngine] = None
rollback_guard: Optional[RollbackGuard] = None
optimized_workflow: Optional[OptimizedWorkflow] = None
scheduler = None  # APScheduler instance


def init_optimizer():
    """Initialize all optimizer components."""
    global optimizer_db, metrics_collector, config_store, experiment_manager
    global improvement_engine, rollback_guard, optimized_workflow

    logger.info("Initializing Self-Improving Optimizer...")

    # Create database
    optimizer_db = Database()

    # Create components
    metrics_collector = MetricsCollector(optimizer_db)
    config_store = ConfigStore(optimizer_db)
    experiment_manager = ExperimentManager(optimizer_db, config_store)
    rollback_guard = RollbackGuard(optimizer_db, config_store, experiment_manager)
    improvement_engine = ImprovementEngine(
        db=optimizer_db,
        metrics=metrics_collector,
        config_store=config_store,
        experiment_manager=experiment_manager,
        perplexity_api_key=Config.PERPLEXITY_API_KEY or "",
        openai_api_key=Config.OPENAI_API_KEY or ""
    )
    optimized_workflow = OptimizedWorkflow(
        db=optimizer_db,
        metrics=metrics_collector,
        config_store=config_store,
        experiment_manager=experiment_manager,
        rollback_guard=rollback_guard,
        openai_api_key=Config.OPENAI_API_KEY
    )

    logger.info("Self-Improving Optimizer initialized successfully!")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global scheduler

    logger.info("Viral News to AI Avatar API starting...")

    # ==========================================================================
    # STEP 1: Validate configuration BEFORE accepting any traffic
    # This catches wrong IDs, missing fields, and other config errors at startup
    # ==========================================================================
    logger.info("Running configuration validation...")
    try:
        await validate_config_or_exit()
    except RuntimeError as e:
        logger.error(f"Configuration validation failed: {e}")
        logger.error("Fix the errors above and restart the application.")
        raise

    # Initialize optimizer
    init_optimizer()

    # Set up daily improvement cycle scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            improvement_engine.run_daily_cycle,
            'cron',
            hour=3,  # Run at 3 AM
            minute=0,
            id='daily_improvement_cycle'
        )
        scheduler.start()
        logger.info("Scheduled daily improvement cycle for 3:00 AM")
    except ImportError:
        logger.warning("APScheduler not installed. Daily improvement cycle disabled.")
        logger.warning("Install with: pip install apscheduler")

    yield

    # Shutdown
    if scheduler:
        scheduler.shutdown()
    logger.info("Shutting down...")

app = FastAPI(
    title="Viral News to AI Avatar",
    description="Automatically create AI avatar videos from trending news",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": "Viral News to AI Avatar",
        "version": "1.0.0"
    }


@app.get("/config")
async def get_config():
    """Check which APIs are configured"""
    return {
        "perplexity": bool(Config.PERPLEXITY_API_KEY),
        "openai": bool(Config.OPENAI_API_KEY),
        "heygen": bool(Config.HEYGEN_API_KEY),
        "heygen_avatar": bool(Config.HEYGEN_AVATAR_ID),
        "heygen_voice": bool(Config.HEYGEN_VOICE_ID),
        "blotato": bool(Config.BLOTATO_API_KEY),
        "industry": Config.INDUSTRY
    }


@app.get("/validate")
async def validate_configuration():
    """
    Run full configuration validation.

    This endpoint runs the same validation that happens at startup.
    Use it to check if your configuration is correct before restarting.

    Returns:
        - passed: True if all checks passed
        - errors: List of configuration errors with fix instructions
        - checks: All validation results
    """
    validator = ConfigValidator()
    report = await validator.validate_all()

    return {
        "passed": report.passed,
        "errors": [
            {
                "service": r.service,
                "check": r.check,
                "message": r.message,
                "fix": r.fix_instruction,
            }
            for r in report.errors
        ],
        "checks": [
            {
                "service": r.service,
                "check": r.check,
                "passed": r.passed,
            }
            for r in report.results
        ],
    }


@app.post("/workflow/run")
async def run_workflow(input_data: WorkflowInput, background_tasks: BackgroundTasks):
    """
    Trigger the full workflow manually.

    This endpoint starts the workflow in the background and returns immediately.
    Use /workflow/status to check progress.
    """
    # For demo purposes, run synchronously
    # In production, use background_tasks or Celery
    result = await run_full_workflow(input_data)
    return result


@app.post("/research")
async def research_news(industry: str = "real estate"):
    """Just run the research step"""
    prompt = f"Research the top 10 trending news items from the past 24 hours in: {industry}"
    result = await call_perplexity(prompt)
    return {"industry": industry, "news": result}


@app.post("/write-script")
async def write_script(news_report: str):
    """Just run the script writing step"""
    result = call_openai_writer(news_report)
    return result.model_dump()


@app.post("/create-video")
async def create_video(script: str, title: str):
    """Just create a HeyGen video"""
    video_id = await create_heygen_video(script, title, Config.HEYGEN_HAS_BACKGROUND)
    return {"video_id": video_id, "status": "processing"}


@app.get("/video-status/{video_id}")
async def check_video_status(video_id: str):
    """Check HeyGen video status"""
    status = await get_heygen_video_status(video_id)
    return status.model_dump()


@app.get("/debug/blotato")
async def debug_blotato():
    """
    Debug Blotato configuration and connectivity.

    Tests:
    1. API key validity
    2. Which account IDs are configured
    3. Media upload with sample video

    Use this to diagnose "no API request" issues.
    """
    results = {
        "api_key_configured": bool(Config.BLOTATO_API_KEY),
        "api_key_format_valid": Config.BLOTATO_API_KEY.startswith("blt_") if Config.BLOTATO_API_KEY else False,
        "accounts": {
            "bluesky": Config.BLOTATO_BLUESKY_ACCOUNT_ID,
            "facebook_account": Config.BLOTATO_FACEBOOK_ACCOUNT_ID,
            "facebook_page": Config.BLOTATO_FACEBOOK_PAGE_ID,
            "youtube": Config.BLOTATO_YOUTUBE_ACCOUNT_ID,
            "instagram": Config.BLOTATO_INSTAGRAM_ACCOUNT_ID,
            "pinterest": Config.BLOTATO_PINTEREST_ACCOUNT_ID,
            "tiktok": Config.BLOTATO_TIKTOK_ACCOUNT_ID,
            "twitter": Config.BLOTATO_TWITTER_ACCOUNT_ID,
        },
        "api_test": None,
        "upload_test": None,
    }

    configured_count = sum(1 for v in results["accounts"].values() if v)
    results["accounts_configured_count"] = configured_count

    if not Config.BLOTATO_API_KEY:
        results["api_test"] = {"status": "skipped", "reason": "No API key configured"}
        results["upload_test"] = {"status": "skipped", "reason": "No API key configured"}
        return results

    test_video_url = "https://database.blotato.io/storage/v1/object/public/public_media/4ddd33eb-e811-4ab5-93e1-2cd0b7e8fb3f/videogen-4c61a730-7eb2-47e9-a3a3-524740a1b877.mp4"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://backend.blotato.com/v2/media",
                headers={
                    "blotato-api-key": Config.BLOTATO_API_KEY,
                    "Content-Type": "application/json"
                },
                json={"url": test_video_url}
            )

            if response.status_code == 200:
                data = response.json()
                results["api_test"] = {"status": "success", "message": "API key is valid"}
                results["upload_test"] = {
                    "status": "success",
                    "returned_url": data.get("url", "No URL returned")
                }
            elif response.status_code == 401:
                results["api_test"] = {
                    "status": "failed",
                    "message": "Invalid API key",
                    "response": response.text
                }
                results["upload_test"] = {"status": "skipped", "reason": "API key invalid"}
            else:
                results["api_test"] = {"status": "unknown", "status_code": response.status_code}
                results["upload_test"] = {
                    "status": "failed",
                    "status_code": response.status_code,
                    "response": response.text
                }
    except Exception as e:
        results["api_test"] = {"status": "error", "message": str(e)}
        results["upload_test"] = {"status": "error", "message": str(e)}

    results["troubleshooting"] = {
        "check_failed_posts": "https://my.blotato.com/failed",
        "check_api_keys": "https://my.blotato.com/settings/api-keys",
        "check_accounts": "https://my.blotato.com/settings/social-accounts",
    }

    return results


@app.post("/debug/blotato/test-all")
async def test_blotato_all_platforms():
    """
    Test posting to ALL platforms with a sample video.

    This uploads a test video and posts to:
    - TikTok (with AI disclosure)
    - Instagram
    - YouTube (with title + synthetic media flag)
    - Facebook (with page ID)
    - Twitter
    - Bluesky

    Usage: curl -X POST http://localhost:8000/debug/blotato/test-all
    """
    results = {
        "test_video": None,
        "upload": None,
        "platforms": {}
    }

    # Test video URL (Blotato's sample video)
    test_video_url = "https://database.blotato.io/storage/v1/object/public/public_media/4ddd33eb-e811-4ab5-93e1-2cd0b7e8fb3f/videogen-4c61a730-7eb2-47e9-a3a3-524740a1b877.mp4"
    test_caption = "Testing Blotato API! #test #automation"
    test_title = "Blotato Test Video"

    results["test_video"] = test_video_url

    # Step 1: Upload media
    logger.info("Test: Uploading media to Blotato...")
    try:
        media_url = await upload_to_blotato(test_video_url)
        results["upload"] = {"status": "success", "media_url": media_url}
        logger.info(f"Test: Upload successful - {media_url}")
    except Exception as e:
        logger.error(f"Test: Upload failed - {e}")
        results["upload"] = {"status": "failed", "error": str(e)}
        return results

    # Step 2: Post to each platform
    platforms_to_test = [
        ("tiktok", Config.BLOTATO_TIKTOK_ACCOUNT_ID),
        ("instagram", Config.BLOTATO_INSTAGRAM_ACCOUNT_ID),
        ("youtube", Config.BLOTATO_YOUTUBE_ACCOUNT_ID),
        ("facebook", Config.BLOTATO_FACEBOOK_ACCOUNT_ID),
        ("twitter", Config.BLOTATO_TWITTER_ACCOUNT_ID),
        ("bluesky", Config.BLOTATO_BLUESKY_ACCOUNT_ID),
    ]

    for platform, account_id in platforms_to_test:
        if not account_id:
            results["platforms"][platform] = {"status": "skipped", "reason": "No account ID configured"}
            logger.warning(f"Test: Skipping {platform} - no account ID")
            continue

        logger.info(f"Test: Posting to {platform} (account: {account_id})...")
        try:
            result = await post_to_platform(
                platform=platform,
                account_id=account_id,
                text=test_caption,
                media_url=media_url,
                title=test_title if platform == "youtube" else None
            )
            results["platforms"][platform] = {"status": "success", "response": result}
            logger.info(f"Test: {platform} SUCCESS")
        except Exception as e:
            results["platforms"][platform] = {"status": "failed", "error": str(e)}
            logger.error(f"Test: {platform} FAILED - {e}")

    # Summary
    success_count = sum(1 for p in results["platforms"].values() if p.get("status") == "success")
    failed_count = sum(1 for p in results["platforms"].values() if p.get("status") == "failed")
    results["summary"] = {
        "total": len(platforms_to_test),
        "success": success_count,
        "failed": failed_count,
        "skipped": len(platforms_to_test) - success_count - failed_count,
        "check_dashboard": "https://my.blotato.com/api-dashboard"
    }

    logger.info(f"Test complete: {success_count} success, {failed_count} failed")
    return results


@app.get("/heygen/talking-photos")
async def list_talking_photos():
    """
    List all talking photos with preview images for avatar selection.

    Use this endpoint to find your correct avatar ID:
    1. Call this endpoint
    2. Look at the image_url for each photo to find yours
    3. Copy the 'id' of your avatar
    4. Set HEYGEN_TALKING_PHOTO_ID in .env
    """
    if not Config.HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HEYGEN_API_KEY not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://api.heygen.com/v1/talking_photo.list",
            headers={"X-Api-Key": Config.HEYGEN_API_KEY}
        )
        response.raise_for_status()
        data = response.json()

        # Return simplified list with just id and image_url
        photos = []
        for photo in data.get("data", []):
            photos.append({
                "id": photo.get("id"),
                "image_url": photo.get("image_url"),
                "is_preset": photo.get("is_preset", False)
            })

        # Separate user's custom photos from presets
        custom_photos = [p for p in photos if not p["is_preset"]]
        preset_photos = [p for p in photos if p["is_preset"]]

        return {
            "current_id": Config.HEYGEN_TALKING_PHOTO_ID,
            "your_photos": custom_photos,
            "preset_photos_count": len(preset_photos),
            "instructions": "Find your avatar in 'your_photos', copy its 'id', and set HEYGEN_TALKING_PHOTO_ID in .env"
        }


# =============================================================================
# OPTIMIZER ENDPOINTS
# =============================================================================

@app.get("/optimizer/status")
async def optimizer_status():
    """Get current optimizer status including health, config, and experiments."""
    if not config_store or not rollback_guard or not experiment_manager:
        return {"status": "not_initialized"}

    return {
        "status": "active",
        "active_config_version": config_store.get_active_config().id,
        "health": rollback_guard.check_health(),
        "running_experiments": [
            {"id": e.id, "name": e.name, "status": e.status}
            for e in experiment_manager.get_running_experiments()
        ]
    }


@app.get("/optimizer/metrics")
async def optimizer_metrics(days: int = 7):
    """Get aggregated workflow metrics for the past N days."""
    if not metrics_collector:
        return {"error": "Optimizer not initialized"}

    return metrics_collector.get_aggregated_metrics(days)


@app.get("/optimizer/experiments")
async def list_experiments():
    """Get all experiments and their results."""
    if not experiment_manager:
        return {"error": "Optimizer not initialized"}

    experiments = experiment_manager.get_all_experiments()
    return {
        "experiments": [
            {
                "id": e.id,
                "name": e.name,
                "status": e.status,
                "hypothesis": e.hypothesis,
                "control_runs": e.control_runs,
                "variant_runs": e.variant_runs,
                "winner": e.winner,
                "statistical_significance": e.statistical_significance
            }
            for e in experiments
        ]
    }


@app.get("/optimizer/config")
async def get_optimizer_config():
    """Get current active configuration."""
    if not config_store:
        return {"error": "Optimizer not initialized"}

    config = config_store.get_active_config()
    return {
        "id": config.id,
        "is_baseline": config.is_baseline,
        "source": config.source,
        "perplexity_model": config.perplexity_model,
        "openai_model": config.openai_model,
        "heygen_voice_speed": config.heygen_voice_speed,
        "heygen_voice_emotion": config.heygen_voice_emotion,
        "improvement_reason": config.improvement_reason
    }


@app.get("/optimizer/config/history")
async def get_config_history(limit: int = 20):
    """Get recent configuration versions."""
    if not config_store:
        return {"error": "Optimizer not initialized"}

    versions = config_store.get_recent_versions(limit)
    return {
        "versions": [
            {
                "id": v.id,
                "is_active": v.is_active,
                "is_baseline": v.is_baseline,
                "source": v.source,
                "improvement_reason": v.improvement_reason
            }
            for v in versions
        ]
    }


@app.post("/optimizer/run-cycle")
async def trigger_improvement_cycle():
    """Manually trigger the daily improvement cycle."""
    if not improvement_engine:
        return {"error": "Optimizer not initialized"}

    result = await improvement_engine.run_daily_cycle()
    return result


@app.post("/optimizer/rollback")
async def manual_rollback():
    """Manually rollback to baseline configuration."""
    if not rollback_guard:
        return {"error": "Optimizer not initialized"}

    baseline_id = rollback_guard.execute_rollback("Manual rollback requested via API")
    return {"status": "rolled_back", "baseline_config_id": baseline_id}


@app.get("/optimizer/health")
async def get_health_summary():
    """Get detailed health summary with daily history."""
    if not rollback_guard:
        return {"error": "Optimizer not initialized"}

    return rollback_guard.get_health_summary()


@app.get("/optimizer/improvements")
async def get_improvements(limit: int = 20):
    """Get recent improvement ideas discovered by the engine."""
    if not improvement_engine:
        return {"error": "Optimizer not initialized"}

    return {
        "improvements": improvement_engine.get_recent_improvements(limit),
        "stats": improvement_engine.get_improvement_stats()
    }


@app.get("/optimizer/changelog")
async def get_changelog(limit: int = 50):
    """Get audit trail of all configuration changes."""
    if not config_store:
        return {"error": "Optimizer not initialized"}

    return {"changes": config_store.get_change_log(limit)}


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

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

# Brand Builder SDK imports
from sdk.apify import ApifyClient, ScrapingConfig, ViralHook, get_parenting_hooks, get_daycare_hooks
from sdk.brand_voice import (
    SCRIPT_WRITER_SYSTEM_PROMPT,
    build_script_prompt,
    build_hook_selector_prompt,
    get_audience,
    HOOK_SELECTOR_SYSTEM_PROMPT,
    AUDIENCE_PARENTS,
    AUDIENCE_DAYCARE,
)

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

    # Enable burned-in video captions/subtitles (adds ~10-30s to processing)
    HEYGEN_ENABLE_CAPTIONS = os.getenv("HEYGEN_ENABLE_CAPTIONS", "true").lower() == "true"

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

    # ==========================================================================
    # BRAND BUILDER CONFIGURATION (Safe Harbor)
    # ==========================================================================
    APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
    WORKFLOW_MODE = os.getenv("WORKFLOW_MODE", "brand")  # "news" or "brand"
    BRAND_NAME = os.getenv("BRAND_NAME", "Safe Harbor Behavioral Health")
    TARGET_AUDIENCE = os.getenv("TARGET_AUDIENCE", "both")  # "parents", "daycare_owners", "both"

    # TikTok hashtags to scrape (comma-separated)
    APIFY_TIKTOK_HASHTAGS = os.getenv(
        "APIFY_TIKTOK_HASHTAGS",
        "momsoftiktok,parentsoftiktok,toddlermom,bigfeelings,daycaretok"
    ).split(",")

    # Reddit subreddits to scrape (comma-separated)
    APIFY_REDDIT_SUBREDDITS = os.getenv(
        "APIFY_REDDIT_SUBREDDITS",
        "Parenting,Mommit,daddit,toddlers,ECEProfessionals,ChildCare"
    ).split(",")


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class WorkflowInput(BaseModel):
    """Input for manual trigger of the workflow"""
    industry: str = Field(default="real estate", description="Industry to research news for")
    script_length_seconds: int = Field(default=15, description="Target video length in seconds")
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


class BrandBuilderInput(BaseModel):
    """Input for brand builder workflow"""
    audience: str = Field(default="parents", description="Target audience: parents, daycare_owners, or both")
    script_length_seconds: int = Field(default=30, description="Target video length in seconds")
    platforms: list[str] = Field(
        default=["tiktok", "instagram", "youtube"],
        description="Social platforms to post to"
    )
    num_hooks_to_fetch: int = Field(default=10, description="Number of viral hooks to scrape")


class BrandContentOutput(BaseModel):
    """Output from brand content generation"""
    selected_hook: str
    hook_source: str
    hook_category: str
    script: str
    caption: str
    title: str


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


def call_openai_writer(news_report: str, script_length_seconds: int = 15) -> ScriptOutput:
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
   - CRITICAL: The script MUST be EXACTLY 3 sentences and no more than 50 words total.
   - Use 6th grade reading level.
   - Balanced viewpoint.
   - First sentence should create an irresistible curiosity gap to hook viewers.
   - The third sentence MUST be: "Hit follow to stay up to date!"
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
        model="gpt-4o",  # Using GPT-4o for reliable JSON output
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
            "speed": 1.1
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
        "title": title,
        "caption": Config.HEYGEN_ENABLE_CAPTIONS  # Burned-in subtitles
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
        # Prefer captioned video URL if available
        return VideoStatus(
            video_id=video_id,
            status=data["status"],
            video_url=data.get("video_url_caption") or data.get("video_url")
        )


async def wait_for_video(video_id: str, max_attempts: int = 60, delay: int = 20) -> str:
    """Poll HeyGen until video is ready (20 min timeout)"""
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
        script_output = call_openai_writer(news_report, input_data.script_length_seconds)
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
# BRAND BUILDER WORKFLOW (Safe Harbor)
# =============================================================================

async def scrape_viral_hooks(num_hooks: int = 10, audience: str = "both") -> list[ViralHook]:
    """Scrape viral hooks from TikTok and Reddit using Apify."""
    if not Config.APIFY_API_TOKEN:
        raise HTTPException(status_code=500, detail="APIFY_API_TOKEN not configured")

    client = ApifyClient(api_token=Config.APIFY_API_TOKEN)

    # Configure scraping based on audience
    if audience == "daycare_owners":
        config = ScrapingConfig(
            tiktok_hashtags=["daycaretok", "preschoolteacher", "ece", "childcarelife", "daycareowner"],
            reddit_subreddits=["ECEProfessionals", "ChildCare", "daycare", "Teachers"],
        )
    elif audience == "parents":
        config = ScrapingConfig(
            tiktok_hashtags=Config.APIFY_TIKTOK_HASHTAGS,
            reddit_subreddits=["Parenting", "Mommit", "daddit", "toddlers", "breakingmom"],
        )
    else:  # both
        config = ScrapingConfig(
            tiktok_hashtags=Config.APIFY_TIKTOK_HASHTAGS,
            reddit_subreddits=Config.APIFY_REDDIT_SUBREDDITS,
        )

    hooks = await client.get_viral_hooks(config=config, top_n=num_hooks)
    return hooks


def select_best_hook(hooks: list[ViralHook], audience: str) -> ViralHook:
    """Use OpenAI to select the best hook for Safe Harbor to respond to."""
    if not Config.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    if not hooks:
        raise HTTPException(status_code=400, detail="No hooks to select from")

    # Get day of week for content calendar
    day_of_week = datetime.now().strftime("%A")

    client = OpenAI(api_key=Config.OPENAI_API_KEY)

    prompt = build_hook_selector_prompt(hooks, audience, day_of_week)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": HOOK_SELECTOR_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )

    content = response.choices[0].message.content

    import json
    try:
        data = json.loads(content)
        selected_index = data.get("selected_index", 1) - 1  # Convert to 0-based
        if 0 <= selected_index < len(hooks):
            return hooks[selected_index]
        return hooks[0]  # Fallback to first hook
    except (json.JSONDecodeError, KeyError):
        logger.warning("Failed to parse hook selection, using first hook")
        return hooks[0]


def write_brand_script(hook: ViralHook, audience: str) -> BrandContentOutput:
    """Write a script in Safe Harbor's voice responding to a viral hook."""
    if not Config.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    audience_config = AUDIENCE_DAYCARE if audience == "daycare_owners" else AUDIENCE_PARENTS
    user_prompt = build_script_prompt(
        hook_text=hook.text,
        source=hook.source,
        source_detail=hook.source_detail,
        audience=audience_config,
    )

    client = OpenAI(api_key=Config.OPENAI_API_KEY)

    # Get the script
    script_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SCRIPT_WRITER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
    )

    script = script_response.choices[0].message.content.strip()

    # Generate caption and title
    caption_prompt = f"""Based on this video script, write:
1. A short, engaging caption (under 200 characters) with 3-5 relevant hashtags
2. A viral title (under 50 characters, no emojis)

Script:
{script}

Return JSON: {{"caption": "...", "title": "..."}}"""

    caption_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": caption_prompt}],
        response_format={"type": "json_object"}
    )

    import json
    try:
        caption_data = json.loads(caption_response.choices[0].message.content)
        caption = caption_data.get("caption", f"{script[:100]}... #safeharbor #parenting")
        title = caption_data.get("title", "Parenting Tip")
    except json.JSONDecodeError:
        caption = f"{script[:100]}... #safeharbor #parenting #bodyandbrain"
        title = "Parenting Wisdom"

    return BrandContentOutput(
        selected_hook=hook.text,
        hook_source=hook.source,
        hook_category=hook.category or "general",
        script=script,
        caption=caption,
        title=title,
    )


async def run_brand_builder_workflow(input_data: BrandBuilderInput) -> dict:
    """Execute the Safe Harbor brand builder workflow."""
    results = {
        "started_at": datetime.now().isoformat(),
        "workflow_type": "brand_builder",
        "audience": input_data.audience,
        "steps": {}
    }

    try:
        # Step 1: Scrape viral hooks
        logger.info(f"Step 1: Scraping viral hooks for {input_data.audience}...")
        hooks = await scrape_viral_hooks(
            num_hooks=input_data.num_hooks_to_fetch,
            audience=input_data.audience
        )
        results["steps"]["scrape_hooks"] = {
            "status": "completed",
            "hooks_found": len(hooks),
            "preview": f"Found {len(hooks)} hooks from TikTok & Reddit"
        }

        if not hooks:
            raise HTTPException(status_code=500, detail="No viral hooks found")

        # Step 2: Select best hook
        logger.info("Step 2: Selecting best hook...")
        selected_hook = select_best_hook(hooks, input_data.audience)
        results["steps"]["select_hook"] = {
            "status": "completed",
            "hook": selected_hook.text,
            "source": selected_hook.source,
            "category": selected_hook.category
        }

        # Step 3: Write script in brand voice
        logger.info("Step 3: Writing script in Safe Harbor voice...")
        content = write_brand_script(selected_hook, input_data.audience)
        results["steps"]["write_script"] = {
            "status": "completed",
            "script_preview": content.script[:150],
            "title": content.title
        }

        # Step 4: Create HeyGen video
        logger.info("Step 4: Creating AI avatar video...")
        video_id = await create_heygen_video(
            script=content.script,
            title=content.title,
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
            "facebook": Config.BLOTATO_FACEBOOK_ACCOUNT_ID,
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
                    text=content.caption,
                    media_url=media_url,
                    title=content.title if platform == "youtube" else None
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

        # Include the full content for reference
        results["content"] = {
            "hook_used": content.selected_hook,
            "script": content.script,
            "caption": content.caption,
            "title": content.title
        }

        results["completed_at"] = datetime.now().isoformat()
        results["status"] = "completed"

    except Exception as e:
        logger.exception("Brand builder workflow failed")
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

    # Initialize optimizer (fast, no HTTP calls)
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

    logger.info("Server ready to accept requests")

    # Server is now ready to accept requests
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
    """Root endpoint"""
    return {
        "status": "healthy",
        "app": "Viral News to AI Avatar",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Fast health check for Railway/container orchestration"""
    return {"status": "ok"}


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


# =============================================================================
# BRAND BUILDER ENDPOINTS (Safe Harbor)
# =============================================================================

@app.get("/config/brand")
async def get_brand_config():
    """Check brand builder configuration"""
    return {
        "workflow_mode": Config.WORKFLOW_MODE,
        "brand_name": Config.BRAND_NAME,
        "target_audience": Config.TARGET_AUDIENCE,
        "apify_configured": bool(Config.APIFY_API_TOKEN),
        "tiktok_hashtags": Config.APIFY_TIKTOK_HASHTAGS,
        "reddit_subreddits": Config.APIFY_REDDIT_SUBREDDITS,
        "heygen_configured": bool(Config.HEYGEN_API_KEY and (Config.HEYGEN_TALKING_PHOTO_ID or Config.HEYGEN_AVATAR_ID)),
        "blotato_configured": bool(Config.BLOTATO_API_KEY),
    }


@app.get("/hooks/scrape")
async def scrape_hooks_preview(
    num_hooks: int = 10,
    audience: str = "parents"
):
    """
    Scrape viral hooks without creating a video.

    Use this to preview available hooks before running the full workflow.

    Args:
        num_hooks: Number of hooks to fetch (default 10)
        audience: Target audience - "parents", "daycare_owners", or "both"

    Returns:
        List of viral hooks with text, source, category, and engagement score
    """
    if not Config.APIFY_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="APIFY_API_TOKEN not configured. Get your token at https://console.apify.com/account/integrations"
        )

    try:
        hooks = await scrape_viral_hooks(num_hooks=num_hooks, audience=audience)
        return {
            "audience": audience,
            "hooks_found": len(hooks),
            "hooks": [
                {
                    "text": h.text,
                    "source": h.source,
                    "source_detail": h.source_detail,
                    "category": h.category,
                    "engagement_score": round(h.engagement_score, 2),
                    "original_url": h.original_url
                }
                for h in hooks
            ]
        }
    except Exception as e:
        logger.exception("Failed to scrape hooks")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/hooks/select")
async def select_hook_preview(
    num_hooks: int = 10,
    audience: str = "parents"
):
    """
    Scrape hooks AND select the best one (preview only, no video).

    This runs steps 1-3 of the brand builder workflow:
    1. Scrape viral hooks
    2. AI selects best hook
    3. Write script in brand voice

    Returns the selected hook and generated script without creating a video.
    """
    if not Config.APIFY_API_TOKEN:
        raise HTTPException(status_code=500, detail="APIFY_API_TOKEN not configured")
    if not Config.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    try:
        # Step 1: Scrape hooks
        hooks = await scrape_viral_hooks(num_hooks=num_hooks, audience=audience)
        if not hooks:
            raise HTTPException(status_code=404, detail="No viral hooks found")

        # Step 2: Select best hook
        selected_hook = select_best_hook(hooks, audience)

        # Step 3: Write script
        content = write_brand_script(selected_hook, audience)

        return {
            "audience": audience,
            "hooks_scraped": len(hooks),
            "selected_hook": {
                "text": selected_hook.text,
                "source": selected_hook.source,
                "source_detail": selected_hook.source_detail,
                "category": selected_hook.category,
                "engagement_score": round(selected_hook.engagement_score, 2)
            },
            "generated_content": {
                "script": content.script,
                "caption": content.caption,
                "title": content.title
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to select hook and write script")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workflow/run-brand")
async def run_brand_workflow(input_data: BrandBuilderInput):
    """
    Run the Safe Harbor brand builder workflow.

    This is the main endpoint for creating brand-building content:
    1. Scrape viral hooks from TikTok and Reddit
    2. AI selects the best hook to respond to
    3. Write script in Safe Harbor's encouraging voice
    4. Create AI avatar video via HeyGen
    5. Post to social platforms via Blotato

    Args:
        audience: "parents", "daycare_owners", or "both" (default: parents)
        script_length_seconds: Target video length (default: 30)
        platforms: List of platforms to post to (default: tiktok, instagram, youtube)
        num_hooks_to_fetch: How many hooks to scrape (default: 10)

    Returns:
        Full workflow results including video URL and post results
    """
    result = await run_brand_builder_workflow(input_data)
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

"""
Blotato SDK - Type-safe Blotato API client with platform-specific contracts.

This SDK prevents the most common Blotato errors:
- Using page_id instead of account_id for Facebook
- Forgetting board_id for Pinterest
- Forgetting page_id for Facebook
- Wrong API key format (must start with blt_)
- Empty media URLs
"""

import logging
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, HttpUrl
import httpx

from .errors import BlotaoError, ConfigurationError

logger = logging.getLogger(__name__)


# =============================================================================
# PLATFORM-SPECIFIC POST MODELS
# =============================================================================


class BasePost(BaseModel):
    """Base class for all platform posts."""

    account_id: str = Field(..., description="Blotato account ID (will be prefixed with acc_ if needed)")
    text: str = Field(..., description="Post caption/text")
    media_url: HttpUrl = Field(..., description="URL to the video/image to post")

    @field_validator("account_id")
    @classmethod
    def ensure_acc_prefix(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("account_id cannot be empty")
        if not v.startswith("acc_"):
            return f"acc_{v}"
        return v

    @field_validator("media_url", mode="before")
    @classmethod
    def validate_media_url(cls, v):
        if not v:
            raise ValueError(
                "media_url cannot be empty. "
                "Make sure your video is fully generated before posting."
            )
        return v


class TikTokPost(BasePost):
    """
    TikTok post with all required fields.

    TikTok requires AI disclosure for AI-generated content.
    """

    is_ai_generated: bool = Field(
        default=True,
        description="Must be True for AI-generated videos (TikTok policy)"
    )
    privacy_level: Literal[
        "PUBLIC_TO_EVERYONE",
        "MUTUAL_FOLLOW_FRIENDS",
        "SELF_ONLY"
    ] = "PUBLIC_TO_EVERYONE"
    disabled_comments: bool = False
    disabled_duet: bool = False
    disabled_stitch: bool = False

    def to_api_payload(self) -> dict:
        return {
            "post": {
                "accountId": self.account_id,
                "content": {
                    "text": self.text,
                    "mediaUrls": [str(self.media_url)],
                    "platform": "tiktok",
                },
                "target": {
                    "targetType": "tiktok",
                    "isAiGenerated": self.is_ai_generated,
                    "privacyLevel": self.privacy_level,
                    "disabledComments": self.disabled_comments,
                    "disabledDuet": self.disabled_duet,
                    "disabledStitch": self.disabled_stitch,
                    "isBrandedContent": False,
                    "isYourBrand": False,
                },
            }
        }


class FacebookPost(BasePost):
    """
    Facebook post - requires BOTH account_id AND page_id.

    This is the most common Blotato error: using page_id as account_id.
    Account ID is your Blotato account, Page ID is your Facebook Page.
    """

    page_id: str = Field(
        ...,
        description="Facebook Page ID (NOT the account ID!). Get from Blotato dashboard."
    )

    @field_validator("page_id")
    @classmethod
    def validate_page_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError(
                "page_id cannot be empty. "
                "Get your Facebook Page ID from Blotato dashboard > Social Accounts."
            )
        return v

    def to_api_payload(self) -> dict:
        return {
            "post": {
                "accountId": self.account_id,
                "content": {
                    "text": self.text,
                    "mediaUrls": [str(self.media_url)],
                    "platform": "facebook",
                },
                "target": {
                    "targetType": "facebook",
                    "pageId": self.page_id,
                },
            }
        }


class InstagramPost(BasePost):
    """Instagram post (Reels)."""

    def to_api_payload(self) -> dict:
        return {
            "post": {
                "accountId": self.account_id,
                "content": {
                    "text": self.text,
                    "mediaUrls": [str(self.media_url)],
                    "platform": "instagram",
                },
                "target": {
                    "targetType": "instagram",
                },
            }
        }


class YouTubePost(BasePost):
    """
    YouTube post - requires title and AI disclosure.

    YouTube requires disclosure for synthetic/AI-generated content.
    """

    title: str = Field(..., description="Video title (required for YouTube)")
    contains_synthetic_media: bool = Field(
        default=True,
        description="Must be True for AI-generated videos (YouTube policy)"
    )
    privacy_status: Literal["public", "unlisted", "private"] = "public"
    notify_subscribers: bool = True

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title cannot be empty for YouTube posts")
        if len(v) > 100:
            raise ValueError(f"title too long ({len(v)} chars). Max 100 characters.")
        return v

    def to_api_payload(self) -> dict:
        return {
            "post": {
                "accountId": self.account_id,
                "content": {
                    "text": self.text,
                    "mediaUrls": [str(self.media_url)],
                    "platform": "youtube",
                },
                "target": {
                    "targetType": "youtube",
                    "title": self.title,
                    "containsSyntheticMedia": self.contains_synthetic_media,
                    "privacyStatus": self.privacy_status,
                    "shouldNotifySubscribers": self.notify_subscribers,
                },
            }
        }


class PinterestPost(BasePost):
    """
    Pinterest post - requires board_id.

    This is a common error: forgetting board_id which is required.
    """

    board_id: str = Field(
        ...,
        description="Pinterest Board ID (required!). Get from Blotato dashboard."
    )

    @field_validator("board_id")
    @classmethod
    def validate_board_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError(
                "board_id cannot be empty. "
                "Get your Pinterest Board ID from Blotato dashboard > Social Accounts."
            )
        return v

    def to_api_payload(self) -> dict:
        return {
            "post": {
                "accountId": self.account_id,
                "content": {
                    "text": self.text,
                    "mediaUrls": [str(self.media_url)],
                    "platform": "pinterest",
                },
                "target": {
                    "targetType": "pinterest",
                    "boardId": self.board_id,
                },
            }
        }


class TwitterPost(BasePost):
    """Twitter/X post."""

    def to_api_payload(self) -> dict:
        return {
            "post": {
                "accountId": self.account_id,
                "content": {
                    "text": self.text,
                    "mediaUrls": [str(self.media_url)],
                    "platform": "twitter",
                },
                "target": {
                    "targetType": "twitter",
                },
            }
        }


class BlueskyPost(BasePost):
    """Bluesky post."""

    def to_api_payload(self) -> dict:
        return {
            "post": {
                "accountId": self.account_id,
                "content": {
                    "text": self.text,
                    "mediaUrls": [str(self.media_url)],
                    "platform": "bluesky",
                },
                "target": {
                    "targetType": "bluesky",
                },
            }
        }


class ThreadsPost(BasePost):
    """Threads post (requires Instagram account connection)."""

    def to_api_payload(self) -> dict:
        return {
            "post": {
                "accountId": self.account_id,
                "content": {
                    "text": self.text,
                    "mediaUrls": [str(self.media_url)],
                    "platform": "threads",
                },
                "target": {
                    "targetType": "threads",
                },
            }
        }


class LinkedInPost(BasePost):
    """LinkedIn post."""

    def to_api_payload(self) -> dict:
        return {
            "post": {
                "accountId": self.account_id,
                "content": {
                    "text": self.text,
                    "mediaUrls": [str(self.media_url)],
                    "platform": "linkedin",
                },
                "target": {
                    "targetType": "linkedin",
                },
            }
        }


# Type alias for any post type
AnyPost = (
    TikTokPost
    | FacebookPost
    | InstagramPost
    | YouTubePost
    | PinterestPost
    | TwitterPost
    | BlueskyPost
    | ThreadsPost
    | LinkedInPost
)


# =============================================================================
# BLOTATO CLIENT
# =============================================================================


class BlotaoClient:
    """
    Type-safe Blotato API client.

    Usage:
        client = BlotaoClient(api_key="blt_your-key")

        # Upload video first
        media_url = await client.upload_media("https://heygen.com/video.mp4")

        # Create platform-specific post (each has required fields)
        post = TikTokPost(
            account_id="12345",
            text="Check this out!",
            media_url=media_url,
            is_ai_generated=True,
        )
        result = await client.post(post)

        # For Facebook, page_id is REQUIRED - can't forget it
        fb_post = FacebookPost(
            account_id="12345",
            page_id="67890",  # Required!
            text="Check this out!",
            media_url=media_url,
        )
        result = await client.post(fb_post)
    """

    def __init__(self, api_key: str, timeout: float = 120.0):
        if not api_key:
            raise ConfigurationError(
                "Blotato API key is not set",
                "Set BLOTATO_API_KEY in your .env file. Get it from https://my.blotato.com/settings/api-keys"
            )

        api_key = api_key.strip()
        if not api_key.startswith("blt_"):
            raise ConfigurationError(
                f"Invalid Blotato API key format: '{api_key[:10]}...'",
                "Blotato API keys must start with 'blt_'. Check https://my.blotato.com/settings/api-keys"
            )

        self.api_key = api_key
        self.timeout = timeout
        self.base_url = "https://backend.blotato.com"

    def _headers(self) -> dict:
        return {
            "blotato-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def upload_media(self, video_url: str) -> str:
        """
        Upload a video to Blotato and get the hosted URL.

        Args:
            video_url: URL to the source video (e.g., from HeyGen)

        Returns:
            Blotato-hosted media URL to use in posts
        """
        if not video_url:
            raise BlotaoError(
                "video_url cannot be empty",
                fix_instruction="Ensure your video is fully generated before uploading"
            )

        logger.info(f"Uploading media to Blotato: {video_url[:50]}...")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v2/media",
                headers=self._headers(),
                json={"url": video_url},
            )

            if response.status_code == 401:
                raise BlotaoError(
                    "Blotato API authentication failed",
                    status_code=401,
                    response_body=response.text,
                    fix_instruction="Check your BLOTATO_API_KEY is valid at https://my.blotato.com/settings/api-keys",
                )

            if response.status_code not in (200, 201):
                raise BlotaoError(
                    "Failed to upload media to Blotato",
                    status_code=response.status_code,
                    response_body=response.text,
                    fix_instruction="Check https://my.blotato.com/failed for error details",
                )

            data = response.json()
            media_url = data.get("url")

            if not media_url:
                raise BlotaoError(
                    "Blotato returned empty media URL",
                    response_body=str(data),
                    fix_instruction="Try uploading again or check video format",
                )

            logger.info(f"Media uploaded successfully: {media_url[:50]}...")
            return media_url

    async def post(self, post: AnyPost) -> dict:
        """
        Post content to a social platform.

        Args:
            post: Platform-specific post object (TikTokPost, FacebookPost, etc.)

        Returns:
            API response dict
        """
        payload = post.to_api_payload()
        platform = payload["post"]["content"]["platform"]

        logger.info(f"Posting to {platform} via Blotato...")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v2/posts",
                headers=self._headers(),
                json=payload,
            )

            logger.info(f"Blotato response for {platform}: {response.status_code}")

            if response.status_code == 401:
                raise BlotaoError(
                    f"Blotato API authentication failed for {platform} post",
                    status_code=401,
                    response_body=response.text,
                    fix_instruction="Check your BLOTATO_API_KEY",
                )

            if response.status_code == 400:
                error_text = response.text.lower()

                # Parse common errors with specific fixes
                fix = "Check https://my.blotato.com/failed for details"

                if "wrong account id" in error_text:
                    fix = (
                        f"Account ID '{post.account_id}' is invalid. "
                        "Get correct ID from Blotato dashboard > Social Accounts > Copy Account ID"
                    )
                elif "boardid" in error_text:
                    fix = "Pinterest requires board_id. Get it from Blotato dashboard."
                elif "pageid" in error_text:
                    fix = "Facebook requires page_id. Get it from Blotato dashboard."
                elif "url is empty" in error_text:
                    fix = "Media URL is empty. Ensure video is fully generated before posting."

                raise BlotaoError(
                    f"Failed to post to {platform}",
                    status_code=400,
                    response_body=response.text,
                    fix_instruction=fix,
                )

            if response.status_code != 200:
                raise BlotaoError(
                    f"Failed to post to {platform}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            result = response.json()
            logger.info(f"Successfully posted to {platform}")
            return result

    async def test_connection(self) -> dict:
        """
        Test Blotato API connection by uploading a sample video.

        Returns:
            dict with connection status and any errors
        """
        test_url = (
            "https://database.blotato.io/storage/v1/object/public/public_media/"
            "4ddd33eb-e811-4ab5-93e1-2cd0b7e8fb3f/"
            "videogen-4c61a730-7eb2-47e9-a3a3-524740a1b877.mp4"
        )

        try:
            media_url = await self.upload_media(test_url)
            return {
                "status": "success",
                "message": "Blotato API connection working",
                "test_media_url": media_url,
            }
        except BlotaoError as e:
            return {
                "status": "failed",
                "message": str(e),
                "fix": e.fix_instruction,
            }
